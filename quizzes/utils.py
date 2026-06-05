"""
Google Docs parser utility.

Extracts questions, options, and answers from a publicly shared Google Doc.

Expected document format:
    1. What is the capital of France?
    a) London
    b) Paris
    c) Berlin
    d) Madrid
    Answer: b

    2. Which planet is closest to the sun?
    a) Venus
    b) Earth
    c) Mercury
    d) Mars
    Answer: c
"""

import re
import requests


def extract_doc_id(url):
    """Extract the Google Doc ID from various URL formats."""
    patterns = [
        r'/document/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def fetch_doc_content(url):
    """
    Fetch text content from a public Google Doc.
    Returns (text_content, error_message) tuple.
    """
    doc_id = extract_doc_id(url)
    if not doc_id:
        return None, "Could not extract document ID from the URL. Please provide a valid Google Docs link."

    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"

    try:
        response = requests.get(export_url, timeout=30)
        if response.status_code == 404:
            return None, "Document not found. Please check the URL."
        if response.status_code == 403:
            return None, (
                "Access denied. Please make sure the document sharing is set to "
                "'Anyone with the link can view'."
            )
        if response.status_code != 200:
            return None, f"Failed to fetch document (HTTP {response.status_code})."

        # Normalise line endings and strip BOM
        text = response.text.replace('\ufeff', '').replace('\r\n', '\n').replace('\r', '\n')
        return text, None

    except requests.Timeout:
        return None, "Request timed out. Please try again."
    except requests.RequestException as e:
        return None, f"Network error: {str(e)}"


def parse_questions(text):
    """
    Parse structured text into a list of question dictionaries.

    Handles:
    - Leading whitespace / formatting characters (* _ spaces)
    - Uppercase or lowercase option letters (A/a, B/b, …)
    - Multi-line options where the option letter stands alone and the text
      continues on the following line(s) (e.g. code-block answers)
    - Answer lines like "Answer: B" or "Answer: B) some text"
    - Separator lines (________________)

    Returns:
        list of dicts: [
            {
                'number': 1,
                'text': 'What is the capital of France?',
                'choices': [
                    {'label': 'a', 'text': 'London'},
                    {'label': 'b', 'text': 'Paris'},
                    ...
                ],
                'answer': 'b'
            },
            ...
        ]
    """
    questions = []
    lines = text.split('\n')

    # Patterns (allow leading whitespace / bold/italic markers)
    question_pattern = re.compile(r'^[*_\s]*(\d+)\s*[.)]\s*(.+)')
    # Allow empty text after the option marker for multi-line (code block) options
    option_pattern = re.compile(r'^[*_\s]*([a-zA-Z])\s*[.)]\s*(.*)')
    answer_pattern = re.compile(r'^[*_\s]*answer\s*[:=]\s*[*_\s]*([a-zA-Z])', re.IGNORECASE)

    def _is_structural(s):
        """Return True if the stripped line is a question, option, or answer marker."""
        return bool(
            question_pattern.match(s)
            or answer_pattern.match(s)
            or re.match(r'^[*_\s]*[a-zA-Z]\s*[.)]\s*', s)
        )

    def _is_separator(s):
        return bool(re.match(r'^[_\-=]{4,}$', s))

    current_question = None
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip blank lines and separator lines
        if not line or _is_separator(line):
            i += 1
            continue

        # ── Question line ────────────────────────────────────────
        q_match = question_pattern.match(line)
        if q_match:
            if current_question and current_question.get('text'):
                questions.append(current_question)
            current_question = {
                'number': int(q_match.group(1)),
                'text': q_match.group(2).strip(),
                'choices': [],
                'answer': None,
            }
            i += 1
            continue

        # ── Answer line ──────────────────────────────────────────
        ans_match = answer_pattern.match(line)
        if ans_match and current_question:
            current_question['answer'] = ans_match.group(1).lower()
            i += 1
            continue

        # ── Option line ──────────────────────────────────────────
        opt_match = option_pattern.match(line)
        if opt_match and current_question:
            label = opt_match.group(1).lower()
            opt_text = opt_match.group(2).strip()

            if not opt_text:
                # Multi-line option: collect following non-structural lines as text
                j = i + 1
                parts = []
                while j < len(lines):
                    nxt = lines[j].strip()
                    j += 1
                    if not nxt or _is_separator(nxt):
                        continue
                    if _is_structural(nxt):
                        j -= 1  # put back so outer loop processes it
                        break
                    parts.append(nxt)
                opt_text = ' '.join(parts) if parts else f'[Option {label.upper()}]'
                i = j
            else:
                i += 1

            current_question['choices'].append({'label': label, 'text': opt_text})
            continue

        # ── Continuation of question text (before any options) ───
        if current_question and not current_question['choices']:
            current_question['text'] += ' ' + line

        i += 1

    # Don't forget the last question
    if current_question and current_question.get('text'):
        questions.append(current_question)

    return questions


def validate_questions(questions):
    """
    Validate parsed questions for completeness.
    Returns (is_valid, errors) tuple.
    """
    errors = []

    if not questions:
        return False, ["No questions could be parsed from the document."]

    for i, q in enumerate(questions):
        q_num = q.get('number', i + 1)

        if not q.get('text'):
            errors.append(f"Question {q_num}: No question text found.")

        if not q.get('choices') or len(q['choices']) < 2:
            errors.append(f"Question {q_num}: At least 2 options are required (found {len(q.get('choices', []))}).")

        if not q.get('answer'):
            errors.append(f"Question {q_num}: No correct answer specified.")
        elif q.get('answer') and q.get('choices'):
            labels = [c['label'] for c in q['choices']]
            if q['answer'] not in labels:
                errors.append(
                    f"Question {q_num}: Answer '{q['answer']}' does not match "
                    f"any option ({', '.join(labels)})."
                )

    return len(errors) == 0, errors


def filter_valid_questions(questions):
    """
    Separate valid questions from invalid ones.

    Returns:
        (valid_questions, skipped_numbers, error_list)
        - valid_questions: list of question dicts that passed all checks
        - skipped_numbers: list of question numbers that were skipped
        - error_list: human-readable error strings for skipped questions
    """
    valid = []
    skipped = []
    errors = []

    for i, q in enumerate(questions):
        q_num = q.get('number', i + 1)
        q_errors = []

        if not q.get('text'):
            q_errors.append("no question text")

        choices = q.get('choices', [])
        if len(choices) < 2:
            q_errors.append(f"only {len(choices)} option(s) found (need ≥ 2)")

        answer = q.get('answer')
        if not answer:
            q_errors.append("no correct answer specified")
        elif choices:
            labels = [c['label'] for c in choices]
            if answer not in labels:
                q_errors.append(f"answer '{answer}' not in option labels ({', '.join(labels)})")

        if q_errors:
            skipped.append(q_num)
            errors.append(f"Q{q_num}: {'; '.join(q_errors)}")
        else:
            valid.append(q)

    return valid, skipped, errors


def import_questions_to_quiz(quiz, questions):
    """
    Save parsed questions to the database.
    Returns the count of successfully imported questions.
    """
    from .models import Question, Choice

    count = 0
    for q_data in questions:
        question = Question.objects.create(
            quiz=quiz,
            text=q_data['text'],
            order=q_data.get('number', count + 1)
        )

        for choice_data in q_data['choices']:
            Choice.objects.create(
                question=question,
                text=choice_data['text'],
                is_correct=(choice_data['label'] == q_data.get('answer', ''))
            )

        count += 1

    return count
