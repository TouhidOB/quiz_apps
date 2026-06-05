"""Seed script to populate the database with sample data."""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quizproject.settings')
django.setup()

from quizzes.models import Department, Quiz, Question, Choice

# ── Departments ──────────────────────────────────────────────

departments_data = [
    {
        'name': 'Software Engineering',
        'description': 'Test your knowledge of programming languages, algorithms, data structures, software design patterns, and development best practices.',
        'icon': 'bi-code-slash',
    },
    {
        'name': 'Civil Engineering',
        'description': 'Quiz yourself on structural analysis, construction materials, geotechnical engineering, and civil infrastructure design.',
        'icon': 'bi-building',
    },
    {
        'name': 'Soil Testing',
        'description': 'Assess your understanding of soil mechanics, classification, laboratory testing procedures, and geotechnical analysis.',
        'icon': 'bi-layers-fill',
    },
    {
        'name': 'Electrical Engineering',
        'description': 'Challenge your knowledge of circuits, electronics, power systems, signal processing, and electrical design.',
        'icon': 'bi-lightning-charge',
    },
    {
        'name': 'Data Science',
        'description': 'Test your skills in statistics, machine learning, data visualization, Python, and analytical thinking.',
        'icon': 'bi-graph-up-arrow',
    },
    {
        'name': 'Networking & Security',
        'description': 'Evaluate your understanding of network protocols, cybersecurity, firewalls, encryption, and system administration.',
        'icon': 'bi-shield-lock-fill',
    },
]

print("Creating departments...")
for d in departments_data:
    dept, created = Department.objects.get_or_create(
        name=d['name'],
        defaults=d
    )
    status = 'Created' if created else 'Exists'
    print(f"  {status}: {dept.name}")

# ── Quizzes with Questions ───────────────────────────────────

se_dept = Department.objects.get(name='Software Engineering')
ce_dept = Department.objects.get(name='Civil Engineering')
ds_dept = Department.objects.get(name='Data Science')

quizzes_data = [
    {
        'department': se_dept,
        'name': 'Python Fundamentals',
        'prerequisites': 'Basic understanding of programming concepts. Familiarity with variables, loops, and functions.',
        'total_questions': 5,
        'mark_per_question': 2,
        'pass_mark': 6,
        'time_limit': 10,
        'is_published': True,
        'questions': [
            {
                'text': 'What is the output of print(type([]))?',
                'choices': [
                    ("<class 'list'>", True),
                    ("<class 'tuple'>", False),
                    ("<class 'dict'>", False),
                    ("<class 'set'>", False),
                ]
            },
            {
                'text': 'Which keyword is used to define a function in Python?',
                'choices': [
                    ('function', False),
                    ('def', True),
                    ('fun', False),
                    ('define', False),
                ]
            },
            {
                'text': 'What does the "len()" function return?',
                'choices': [
                    ('The type of an object', False),
                    ('The value of an object', False),
                    ('The number of items in an object', True),
                    ('The memory address of an object', False),
                ]
            },
            {
                'text': 'Which of the following is immutable in Python?',
                'choices': [
                    ('List', False),
                    ('Dictionary', False),
                    ('Set', False),
                    ('Tuple', True),
                ]
            },
            {
                'text': 'What is the correct way to create a dictionary in Python?',
                'choices': [
                    ('d = []', False),
                    ('d = {}', True),
                    ('d = ()', False),
                    ('d = <>', False),
                ]
            },
        ]
    },
    {
        'department': se_dept,
        'name': 'JavaScript Essentials',
        'prerequisites': 'Basic HTML knowledge. Understanding of web browsers and how websites work.',
        'total_questions': 5,
        'mark_per_question': 2,
        'pass_mark': 6,
        'time_limit': 10,
        'is_published': True,
        'questions': [
            {
                'text': 'Which company developed JavaScript?',
                'choices': [
                    ('Microsoft', False),
                    ('Netscape', True),
                    ('Google', False),
                    ('Apple', False),
                ]
            },
            {
                'text': 'What is the correct syntax for referring to an external script called "app.js"?',
                'choices': [
                    ('<script href="app.js">', False),
                    ('<script name="app.js">', False),
                    ('<script src="app.js">', True),
                    ('<script file="app.js">', False),
                ]
            },
            {
                'text': 'How do you write "Hello World" in an alert box?',
                'choices': [
                    ('msg("Hello World")', False),
                    ('alert("Hello World")', True),
                    ('alertBox("Hello World")', False),
                    ('msgBox("Hello World")', False),
                ]
            },
            {
                'text': 'Which operator is used for strict equality in JavaScript?',
                'choices': [
                    ('==', False),
                    ('===', True),
                    ('!=', False),
                    ('=', False),
                ]
            },
            {
                'text': 'What does "NaN" stand for in JavaScript?',
                'choices': [
                    ('Not a Null', False),
                    ('Not a Number', True),
                    ('Null and None', False),
                    ('Number and Null', False),
                ]
            },
        ]
    },
    {
        'department': ce_dept,
        'name': 'Structural Analysis Basics',
        'prerequisites': 'Knowledge of physics, mechanics of materials, and basic mathematics including calculus.',
        'total_questions': 5,
        'mark_per_question': 2,
        'pass_mark': 6,
        'time_limit': 15,
        'is_published': True,
        'questions': [
            {
                'text': 'What is the unit of stress in the SI system?',
                'choices': [
                    ('Newton', False),
                    ('Pascal', True),
                    ('Joule', False),
                    ('Watt', False),
                ]
            },
            {
                'text': 'A simply supported beam has how many supports?',
                'choices': [
                    ('1', False),
                    ('2', True),
                    ('3', False),
                    ('4', False),
                ]
            },
            {
                'text': "What does Young's modulus measure?",
                'choices': [
                    ('Thermal conductivity', False),
                    ('Stiffness of a material', True),
                    ('Density', False),
                    ('Hardness', False),
                ]
            },
            {
                'text': 'What type of force causes a member to shorten?',
                'choices': [
                    ('Tension', False),
                    ('Shear', False),
                    ('Compression', True),
                    ('Torsion', False),
                ]
            },
            {
                'text': 'The bending moment at the supports of a simply supported beam is:',
                'choices': [
                    ('Maximum', False),
                    ('Zero', True),
                    ('Uniform', False),
                    ('Negative', False),
                ]
            },
        ]
    },
    {
        'department': ds_dept,
        'name': 'Machine Learning Foundations',
        'prerequisites': 'Understanding of statistics, linear algebra, and basic Python programming. Familiarity with NumPy and pandas is helpful.',
        'total_questions': 5,
        'mark_per_question': 2,
        'pass_mark': 6,
        'time_limit': 12,
        'is_published': True,
        'questions': [
            {
                'text': 'Which type of learning uses labeled data?',
                'choices': [
                    ('Unsupervised Learning', False),
                    ('Supervised Learning', True),
                    ('Reinforcement Learning', False),
                    ('Transfer Learning', False),
                ]
            },
            {
                'text': 'What is overfitting?',
                'choices': [
                    ('Model performs well on training data but poorly on test data', True),
                    ('Model performs poorly on both training and test data', False),
                    ('Model has too few parameters', False),
                    ('Model ignores the training data', False),
                ]
            },
            {
                'text': 'Which algorithm is used for classification?',
                'choices': [
                    ('Linear Regression', False),
                    ('K-Means', False),
                    ('Random Forest', True),
                    ('PCA', False),
                ]
            },
            {
                'text': 'What does "epoch" mean in neural networks?',
                'choices': [
                    ('One pass through the entire training dataset', True),
                    ('A single weight update', False),
                    ('A layer in the network', False),
                    ('The learning rate', False),
                ]
            },
            {
                'text': 'Which metric is best for imbalanced classification problems?',
                'choices': [
                    ('Accuracy', False),
                    ('F1 Score', True),
                    ('MSE', False),
                    ('R-squared', False),
                ]
            },
        ]
    },
]

print("\nCreating quizzes and questions...")
for q_data in quizzes_data:
    questions = q_data.pop('questions')
    quiz, created = Quiz.objects.get_or_create(
        name=q_data['name'],
        defaults=q_data
    )
    status = 'Created' if created else 'Exists'
    print(f"  {status}: {quiz.name}")

    if created:
        for i, q in enumerate(questions, 1):
            question = Question.objects.create(
                quiz=quiz,
                text=q['text'],
                order=i
            )
            for choice_text, is_correct in q['choices']:
                Choice.objects.create(
                    question=question,
                    text=choice_text,
                    is_correct=is_correct
                )
        print(f"    → Added {len(questions)} questions")

print("\n✅ Seeding complete!")
