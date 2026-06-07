from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Avg, Count, Max, F, Q, Sum, ExpressionWrapper, FloatField
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings as django_settings
from django.urls import reverse

import random
import uuid
import logging

logger = logging.getLogger(__name__)

from functools import wraps
from decimal import Decimal

from .models import (
    Department, Quiz, Question, Choice,
    QuizAttempt, UserAnswer, GoogleDocUpload,
    Package, PackagePurchase, BookmarkedQuestion,
    VendorProfile, SubCategory, PlatformSetting,
    QuizPurchase, VendorSale,
)
from .forms import (
    GoogleDocUploadForm, UserRegisterForm,
    DepartmentForm, QuizForm, ManualQuestionForm, EmployeeForm,
    QuestionEditForm, PackageForm, CSVJSONUploadForm,
    VendorRegisterForm, VendorQuizForm, SubCategoryForm,
    VendorCategoryForm, VendorPackageForm, PlatformSettingForm,
)
from .utils import fetch_doc_content, parse_questions, validate_questions, filter_valid_questions, import_questions_to_quiz


# ─── Vendor Access Control & Shared Helpers ──────────────────

def get_vendor_profile(user):
    """Return the user's VendorProfile or None."""
    if not user.is_authenticated:
        return None
    return VendorProfile.objects.filter(user=user).first()


def vendor_required(view_func):
    """Decorator allowing only users with an APPROVED VendorProfile. Others are
    redirected to registration or the pending page."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")
        profile = get_vendor_profile(request.user)
        if profile is None:
            messages.info(request, 'Register as a vendor to access the vendor dashboard.')
            return redirect('vendor_register')
        if not profile.is_approved:
            return redirect('vendor_pending')
        return view_func(request, *args, profile=profile, **kwargs)
    return _wrapped


def user_can_access_quiz(user, quiz):
    """Return True if the user is allowed to take this quiz."""
    if not quiz.is_paid:
        return True
    if not user.is_authenticated:
        return False
    if user.is_staff or quiz.owner_id == user.id:
        return True
    if QuizPurchase.objects.filter(
        user=user, quiz=quiz, payment_status='completed'
    ).exists():
        return True
    # Access via a completed package purchase that includes this quiz
    return PackagePurchase.objects.filter(
        user=user, payment_status='completed', package__quizzes=quiz
    ).exists()


def record_vendor_sale(*, purchase, sale_type):
    """Create a VendorSale ledger row for a completed vendor-owned purchase.
    Idempotent — does nothing if the item has no vendor owner or a sale already exists."""
    if sale_type == 'quiz':
        item = purchase.quiz
        if item.owner_id is None:
            return None
        if VendorSale.objects.filter(quiz_purchase=purchase).exists():
            return None
    else:
        item = purchase.package
        if item.owner_id is None:
            return None
        if VendorSale.objects.filter(package_purchase=purchase).exists():
            return None

    fee = PlatformSetting.load().vendor_fee_per_sale or Decimal('0.00')
    amount = purchase.amount_paid or Decimal('0.00')
    earning = amount - fee
    if earning < 0:
        earning = Decimal('0.00')

    return VendorSale.objects.create(
        vendor=item.owner,
        buyer=purchase.user,
        sale_type=sale_type,
        quiz=item if sale_type == 'quiz' else None,
        package=item if sale_type == 'package' else None,
        quiz_purchase=purchase if sale_type == 'quiz' else None,
        package_purchase=purchase if sale_type == 'package' else None,
        sale_amount=amount,
        platform_fee=fee,
        vendor_earning=earning,
    )


# ─── Public Pages ────────────────────────────────────────────

def home(request):
    """Landing page with department cards and stats."""
    departments = Department.objects.filter(is_active=True, is_approved=True)
    total_quizzes = Quiz.objects.filter(is_published=True).count()
    total_attempts = QuizAttempt.objects.count()
    total_departments = departments.count()

    context = {
        'departments': departments,
        'total_quizzes': total_quizzes,
        'total_attempts': total_attempts,
        'total_departments': total_departments,
    }
    return render(request, 'quizzes/home.html', context)


def about_view(request):
    """About page with platform information and stats."""
    context = {
        'total_departments': Department.objects.filter(is_active=True, is_approved=True).count(),
        'total_quizzes': Quiz.objects.filter(is_published=True).count(),
        'total_questions': Question.objects.count(),
        'total_attempts': QuizAttempt.objects.count(),
    }
    return render(request, 'quizzes/about.html', context)


def contact_view(request):
    """Contact page with form submission."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if name and email and subject and message:
            messages.success(
                request,
                f'Thank you, {name}! Your message has been received. '
                f'We\'ll get back to you at {email} within 24 hours.'
            )
        else:
            messages.error(request, 'Please fill in all fields.')
        return redirect('contact')

    return render(request, 'quizzes/contact.html')


def terms_view(request):
    """Terms and Conditions page."""
    return render(request, 'quizzes/terms.html')


def privacy_view(request):
    """Privacy Policy page."""
    return render(request, 'quizzes/privacy.html')


def faq_view(request):
    """Frequently Asked Questions page."""
    return render(request, 'quizzes/faq.html')


def departments_view(request):
    """Dedicated page listing all departments with stats."""
    departments = (
        Department.objects
        .filter(is_active=True, is_approved=True)
        .annotate(
            quiz_count_val=Count('quizzes', filter=Q(quizzes__is_published=True)),
            question_count=Count('quizzes__questions', filter=Q(quizzes__is_published=True)),
            attempt_count=Count('quizzes__attempts', filter=Q(quizzes__is_published=True)),
        )
        .order_by('name')
    )
    context = {
        'departments': departments,
        'total_departments': departments.count(),
        'total_quizzes': Quiz.objects.filter(is_published=True).count(),
        'total_questions': Question.objects.count(),
    }
    return render(request, 'quizzes/departments.html', context)


def department_quizzes(request, slug):
    """List all published quizzes in a department."""
    department = get_object_or_404(Department, slug=slug, is_active=True, is_approved=True)
    quizzes = department.quizzes.filter(is_published=True)

    if request.user.is_authenticated:
        for quiz in quizzes:
            quiz.user_attempts = QuizAttempt.objects.filter(
                user=request.user, quiz=quiz
            ).count()
            best = QuizAttempt.objects.filter(
                user=request.user, quiz=quiz
            ).order_by('-score').first()
            quiz.best_score = best.score if best else None
            quiz.user_passed = best.passed if best else False

    context = {
        'department': department,
        'quizzes': quizzes,
    }
    return render(request, 'quizzes/quiz_list.html', context)


def quiz_detail(request, slug):
    """Quiz information page with prerequisites and stats."""
    quiz = get_object_or_404(Quiz, slug=slug, is_published=True)

    user_attempts = []
    can_take = True
    if request.user.is_authenticated:
        user_attempts = QuizAttempt.objects.filter(
            user=request.user, quiz=quiz
        )[:5]
        if not quiz.allow_retake and user_attempts.exists():
            can_take = False

    attempt_count = QuizAttempt.objects.filter(quiz=quiz).count()
    pass_count = QuizAttempt.objects.filter(quiz=quiz, passed=True).count()
    avg_score = QuizAttempt.objects.filter(quiz=quiz).aggregate(
        avg=Avg('score')
    )['avg']

    has_access = user_can_access_quiz(request.user, quiz)

    context = {
        'quiz': quiz,
        'user_attempts': user_attempts,
        'can_take': can_take,
        'has_access': has_access,
        'needs_purchase': quiz.is_paid and not has_access,
        'attempt_count': attempt_count,
        'pass_count': pass_count,
        'pass_rate': round((pass_count / attempt_count) * 100, 1) if attempt_count > 0 else 0,
        'avg_score': round(avg_score, 1) if avg_score else 0,
    }
    return render(request, 'quizzes/quiz_detail.html', context)


@login_required
def take_quiz(request, slug):
    """Start/display a quiz with timer."""
    quiz = get_object_or_404(Quiz, slug=slug, is_published=True)

    if not user_can_access_quiz(request.user, quiz):
        messages.warning(request, 'This is a paid quiz. Please purchase it to start.')
        return redirect('quiz_detail', slug=slug)

    if not quiz.allow_retake:
        existing = QuizAttempt.objects.filter(user=request.user, quiz=quiz).exists()
        if existing:
            messages.warning(request, 'You have already taken this quiz. Retakes are not allowed.')
            return redirect('quiz_detail', slug=slug)

    if not quiz.has_enough_questions:
        messages.error(request, 'This quiz does not have enough questions yet.')
        return redirect('quiz_detail', slug=slug)

    all_questions = list(quiz.questions.prefetch_related('choices').all())
    random.shuffle(all_questions)  # always randomize for fair selection

    # Pick only the configured number of questions from the full pool
    selected_questions = all_questions[:quiz.total_questions]

    for q in selected_questions:
        q.shuffled_choices = list(q.choices.all())
        random.shuffle(q.shuffled_choices)

    # Collect selected question IDs so submit_quiz knows exactly which ones were shown
    selected_ids = ','.join(str(q.id) for q in selected_questions)

    context = {
        'quiz': quiz,
        'questions': selected_questions,
        'selected_ids': selected_ids,
        'time_limit_seconds': quiz.time_limit * 60,
    }
    return render(request, 'quizzes/take_quiz.html', context)


@login_required
def submit_quiz(request, slug):
    """Process quiz submission and calculate score."""
    if request.method != 'POST':
        return redirect('take_quiz', slug=slug)

    quiz = get_object_or_404(Quiz, slug=slug, is_published=True)

    with transaction.atomic():
        # Get only the questions that were actually shown to this user
        selected_ids_str = request.POST.get('selected_question_ids', '')
        if selected_ids_str:
            question_ids = [int(qid) for qid in selected_ids_str.split(',') if qid.strip()]
            questions = Question.objects.filter(id__in=question_ids, quiz=quiz)
        else:
            # Fallback: use all questions (legacy behaviour)
            questions = quiz.questions.all()

        num_questions = questions.count()
        total_marks = num_questions * float(quiz.mark_per_question)

        attempt = QuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            total_marks=total_marks,
        )

        score = 0
        for question in questions:
            choice_id = request.POST.get(f'question_{question.id}')
            selected_choice = None

            if choice_id:
                try:
                    selected_choice = Choice.objects.get(
                        id=choice_id,
                        question=question
                    )
                    if selected_choice.is_correct:
                        score += float(quiz.mark_per_question)
                except Choice.DoesNotExist:
                    pass

            UserAnswer.objects.create(
                attempt=attempt,
                question=question,
                selected_choice=selected_choice
            )

        attempt.score = score
        attempt.passed = score >= float(quiz.pass_mark)
        attempt.completed_at = timezone.now()
        attempt.save()

    return redirect('quiz_result', attempt_id=attempt.id)


@login_required
def quiz_result(request, attempt_id):
    """Display quiz results with detailed breakdown."""
    attempt = get_object_or_404(
        QuizAttempt,
        id=attempt_id,
        user=request.user
    )

    answers = attempt.answers.select_related(
        'question', 'selected_choice'
    ).order_by('question__order')

    results = []
    for answer in answers:
        correct_choice = answer.question.choices.filter(is_correct=True).first()
        results.append({
            'question': answer.question,
            'selected': answer.selected_choice,
            'correct': correct_choice,
            'is_correct': answer.is_correct,
            'choices': answer.question.choices.all(),
        })

    total_shown = len(results)
    unanswered_count = sum(1 for r in results if r['selected'] is None)

    # Get bookmarked question IDs for this user
    bookmarked_ids = set()
    if request.user.is_authenticated:
        bookmarked_ids = set(
            BookmarkedQuestion.objects.filter(
                user=request.user,
                question__in=[r['question'] for r in results]
            ).values_list('question_id', flat=True)
        )

    context = {
        'attempt': attempt,
        'results': results,
        'quiz': attempt.quiz,
        'total_shown': total_shown,
        'unanswered_count': unanswered_count,
        'bookmarked_ids': bookmarked_ids,
    }
    return render(request, 'quizzes/quiz_result.html', context)


# ─── Question Upload ────────────────────────────────────────

@staff_member_required
def upload_questions(request, slug):
    """Upload questions from a Google Docs link."""
    quiz = get_object_or_404(Quiz, slug=slug)

    if request.method == 'POST':
        form = GoogleDocUploadForm(request.POST)
        if form.is_valid():
            doc_url = form.cleaned_data['doc_url']
            clear_existing = form.cleaned_data['clear_existing']

            upload = GoogleDocUpload.objects.create(
                quiz=quiz,
                doc_url=doc_url,
                uploaded_by=request.user,
                status='processing'
            )

            content, error = fetch_doc_content(doc_url)
            if error:
                upload.status = 'failed'
                upload.error_message = error
                upload.save()
                messages.error(request, f'Failed to fetch document: {error}')
                return render(request, 'quizzes/upload_questions.html', {
                    'form': form, 'quiz': quiz, 'upload': upload
                })

            all_questions = parse_questions(content)
            if not all_questions:
                upload.status = 'failed'
                upload.error_message = 'No questions could be parsed from the document.'
                upload.save()
                messages.error(request, 'No questions could be parsed. Check the document format.')
                return render(request, 'quizzes/upload_questions.html', {
                    'form': form, 'quiz': quiz, 'upload': upload
                })

            valid_questions, skipped_nums, skip_errors = filter_valid_questions(all_questions)

            if not valid_questions:
                upload.status = 'failed'
                upload.error_message = '\n'.join(skip_errors)
                upload.save()
                messages.error(
                    request,
                    f'No valid questions found. {len(skip_errors)} error(s) detected.'
                )
                return render(request, 'quizzes/upload_questions.html', {
                    'form': form, 'quiz': quiz, 'upload': upload,
                    'parse_errors': skip_errors
                })

            if clear_existing:
                quiz.questions.all().delete()

            with transaction.atomic():
                count = import_questions_to_quiz(quiz, valid_questions)
                upload.status = 'success'
                upload.questions_imported = count
                upload.save()

            if skipped_nums:
                messages.warning(
                    request,
                    f'Imported {count} question(s). '
                    f'Skipped {len(skipped_nums)} malformed question(s): {skipped_nums[:10]}.'
                )
            else:
                messages.success(
                    request,
                    f'Successfully imported {count} question(s) from Google Docs!'
                )
            return redirect('upload_questions', slug=slug)
    else:
        form = GoogleDocUploadForm()

    uploads = GoogleDocUpload.objects.filter(quiz=quiz)[:10]

    context = {
        'form': form,
        'quiz': quiz,
        'uploads': uploads,
    }
    return render(request, 'quizzes/upload_questions.html', context)


# ─── Leaderboard (FIXED) ─────────────────────────────────────

def leaderboard(request):
    """Global or quiz-specific leaderboard showing top scores."""
    quiz_id = request.GET.get('quiz')
    selected_quiz = None

    attempts_qs = (
        QuizAttempt.objects
        .filter(passed=True, completed_at__isnull=False)
        .select_related('user', 'quiz', 'quiz__department')
        .annotate(
            calc_percentage=ExpressionWrapper(
                F('score') * 100.0 / F('total_marks'),
                output_field=FloatField()
            )
        )
    )

    if quiz_id:
        try:
            selected_quiz = Quiz.objects.get(pk=quiz_id)
            attempts_qs = attempts_qs.filter(quiz=selected_quiz)
        except Quiz.DoesNotExist:
            pass

    top_attempts = attempts_qs.order_by('-score', 'completed_at')[:50]
    all_quizzes = Quiz.objects.filter(is_published=True).order_by('name')

    context = {
        'top_attempts': top_attempts,
        'all_quizzes': all_quizzes,
        'selected_quiz': selected_quiz,
    }
    return render(request, 'quizzes/leaderboard.html', context)


# ─── Authentication ──────────────────────────────────────────

def register_view(request):
    """User registration."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}! Your account has been created.')
            return redirect('home')
    else:
        form = UserRegisterForm()

    return render(request, 'quizzes/register.html', {'form': form})


def login_view(request):
    """User login."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            next_url = request.GET.get('next', 'home')
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            return redirect(next_url)
    else:
        form = AuthenticationForm()

    return render(request, 'quizzes/login.html', {'form': form})


def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')



# ═══════════════════════════════════════════════════════════════
# CUSTOM ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════

@staff_member_required
def dashboard(request):
    """Main admin dashboard overview."""
    total_departments = Department.objects.count()
    total_quizzes = Quiz.objects.count()
    total_questions = Question.objects.count()
    total_users = User.objects.count()
    total_attempts = QuizAttempt.objects.count()
    total_passed = QuizAttempt.objects.filter(passed=True).count()
    staff_count = User.objects.filter(is_staff=True).count()

    recent_attempts = (
        QuizAttempt.objects
        .select_related('user', 'quiz')
        .order_by('-started_at')[:8]
    )
    recent_uploads = (
        GoogleDocUpload.objects
        .select_related('quiz', 'uploaded_by')
        .order_by('-created_at')[:5]
    )

    # Quizzes needing questions
    quizzes_needing_qs = []
    for quiz in Quiz.objects.select_related('department').all():
        if quiz.question_count < quiz.total_questions:
            quizzes_needing_qs.append(quiz)

    context = {
        'active_page': 'overview',
        'total_departments': total_departments,
        'total_quizzes': total_quizzes,
        'total_questions': total_questions,
        'total_users': total_users,
        'total_attempts': total_attempts,
        'total_passed': total_passed,
        'staff_count': staff_count,
        'pass_rate': round((total_passed / total_attempts) * 100, 1) if total_attempts > 0 else 0,
        'recent_attempts': recent_attempts,
        'recent_uploads': recent_uploads,
        'quizzes_needing_qs': quizzes_needing_qs,
    }
    return render(request, 'quizzes/dashboard/index.html', context)


# ─── Department CRUD ────────────────────────────────────────

@staff_member_required
def dashboard_departments(request):
    """List all departments."""
    departments = Department.objects.annotate(
        quiz_total=Count('quizzes')
    ).order_by('name')
    context = {'departments': departments, 'active_page': 'departments'}
    return render(request, 'quizzes/dashboard/departments.html', context)


@staff_member_required
def dashboard_department_create(request):
    """Create a new department."""
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Department "{form.cleaned_data["name"]}" created successfully!')
            return redirect('dashboard_departments')
    else:
        form = DepartmentForm()
    return render(request, 'quizzes/dashboard/department_form.html', {
        'form': form, 'action': 'Create'
    })


@staff_member_required
def dashboard_department_edit(request, pk):
    """Edit an existing department."""
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            messages.success(request, f'Department "{department.name}" updated successfully!')
            return redirect('dashboard_departments')
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'quizzes/dashboard/department_form.html', {
        'form': form, 'action': 'Edit', 'department': department
    })


@staff_member_required
def dashboard_department_delete(request, pk):
    """Delete a department."""
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        name = department.name
        department.delete()
        messages.success(request, f'Department "{name}" deleted.')
        return redirect('dashboard_departments')
    return render(request, 'quizzes/dashboard/department_confirm_delete.html', {
        'department': department
    })


# ─── Quiz CRUD ──────────────────────────────────────────────

@staff_member_required
def dashboard_quizzes(request):
    """List all quizzes."""
    quizzes = Quiz.objects.select_related('department').order_by('-created_at')
    context = {'quizzes': quizzes, 'active_page': 'quizzes'}
    return render(request, 'quizzes/dashboard/quizzes.html', context)


@staff_member_required
def dashboard_quiz_create(request):
    """Create a new quiz."""
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Quiz "{form.cleaned_data["name"]}" created successfully!')
            return redirect('dashboard_quizzes')
    else:
        form = QuizForm()
    return render(request, 'quizzes/dashboard/quiz_form.html', {
        'form': form, 'action': 'Create', 'active_page': 'quizzes'
    })


@staff_member_required
def dashboard_quiz_edit(request, pk):
    """Edit an existing quiz."""
    quiz = get_object_or_404(Quiz, pk=pk)
    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, f'Quiz "{quiz.name}" updated successfully!')
            return redirect('dashboard_quizzes')
    else:
        form = QuizForm(instance=quiz)
    return render(request, 'quizzes/dashboard/quiz_form.html', {
        'form': form, 'action': 'Edit', 'quiz': quiz, 'active_page': 'quizzes'
    })


@staff_member_required
def dashboard_quiz_delete(request, pk):
    """Delete a quiz."""
    quiz = get_object_or_404(Quiz, pk=pk)
    if request.method == 'POST':
        name = quiz.name
        quiz.delete()
        messages.success(request, f'Quiz "{name}" deleted.')
        return redirect('dashboard_quizzes')
    return render(request, 'quizzes/dashboard/quiz_confirm_delete.html', {
        'quiz': quiz
    })


# ─── Question Management ────────────────────────────────────

@staff_member_required
def dashboard_quiz_questions(request, pk):
    """Manage questions for a specific quiz — manual add + Google Docs upload."""
    quiz = get_object_or_404(Quiz, pk=pk)
    questions = quiz.questions.prefetch_related('choices').all()

    manual_form = ManualQuestionForm()
    gdoc_form = GoogleDocUploadForm()
    uploads = GoogleDocUpload.objects.filter(quiz=quiz)[:5]

    context = {
        'quiz': quiz,
        'questions': questions,
        'manual_form': manual_form,
        'gdoc_form': gdoc_form,
        'uploads': uploads,
        'active_page': 'quizzes',
    }
    return render(request, 'quizzes/dashboard/quiz_questions.html', context)


@staff_member_required
def dashboard_add_question_manual(request, pk):
    """Add a single question manually."""
    quiz = get_object_or_404(Quiz, pk=pk)

    if request.method == 'POST':
        form = ManualQuestionForm(request.POST)
        if form.is_valid():
            # Determine next order number
            last_order = quiz.questions.order_by('-order').values_list('order', flat=True).first() or 0

            question = Question.objects.create(
                quiz=quiz,
                text=form.cleaned_data['question_text'],
                order=last_order + 1
            )

            correct = form.cleaned_data['correct_answer']

            for label_key in ['a', 'b', 'c', 'd']:
                field_name = f'choice_{label_key}'
                text = form.cleaned_data.get(field_name, '').strip()
                if text:
                    Choice.objects.create(
                        question=question,
                        text=text,
                        is_correct=(label_key == correct)
                    )

            messages.success(request, 'Question added successfully!')
        else:
            messages.error(request, 'Please fix the errors below.')

    return redirect('dashboard_quiz_questions', pk=pk)


@staff_member_required
def dashboard_add_question_gdoc(request, pk):
    """Upload questions from Google Docs."""
    quiz = get_object_or_404(Quiz, pk=pk)

    if request.method == 'POST':
        form = GoogleDocUploadForm(request.POST)
        if form.is_valid():
            doc_url = form.cleaned_data['doc_url']
            clear_existing = form.cleaned_data['clear_existing']

            upload = GoogleDocUpload.objects.create(
                quiz=quiz,
                doc_url=doc_url,
                uploaded_by=request.user,
                status='processing'
            )

            content, error = fetch_doc_content(doc_url)
            if error:
                upload.status = 'failed'
                upload.error_message = error
                upload.save()
                messages.error(request, f'Failed to fetch document: {error}')
                return redirect('dashboard_quiz_questions', pk=pk)

            all_parsed = parse_questions(content)
            if not all_parsed:
                upload.status = 'failed'
                upload.error_message = 'No questions could be parsed from the document.'
                upload.save()
                messages.error(request, 'No questions could be parsed. Check the document format.')
                return redirect('dashboard_quiz_questions', pk=pk)

            valid_parsed, skipped_nums, skip_errors = filter_valid_questions(all_parsed)

            if not valid_parsed:
                upload.status = 'failed'
                upload.error_message = '\n'.join(skip_errors)
                upload.save()
                messages.error(request, f'No valid questions found. {len(skip_errors)} error(s) detected.')
                return redirect('dashboard_quiz_questions', pk=pk)

            if clear_existing:
                quiz.questions.all().delete()

            with transaction.atomic():
                count = import_questions_to_quiz(quiz, valid_parsed)
                upload.status = 'success'
                upload.questions_imported = count
                upload.save()

            if skipped_nums:
                messages.warning(
                    request,
                    f'Imported {count} question(s). '
                    f'Skipped {len(skipped_nums)} malformed question(s): {skipped_nums[:10]}.'
                )
            else:
                messages.success(request, f'Successfully imported {count} question(s) from Google Docs!')

    return redirect('dashboard_quiz_questions', pk=pk)


@staff_member_required
def dashboard_delete_question(request, pk):
    """Delete a single question."""
    question = get_object_or_404(Question, pk=pk)
    quiz_pk = question.quiz.pk
    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Question deleted.')
    return redirect('dashboard_quiz_questions', pk=quiz_pk)


# ─── Employee Management ────────────────────────────────────

@staff_member_required
def dashboard_employees(request):
    """List all staff/admin users."""
    employees = User.objects.filter(is_staff=True).order_by('-date_joined')
    context = {'employees': employees, 'active_page': 'employees'}
    return render(request, 'quizzes/dashboard/employees.html', context)


@staff_member_required
def dashboard_employee_create(request):
    """Add a new employee/staff member."""
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Employee "{user.get_full_name()}" added successfully!')
            return redirect('dashboard_employees')
    else:
        form = EmployeeForm()
    return render(request, 'quizzes/dashboard/employee_form.html', {
        'form': form, 'action': 'Add', 'active_page': 'employees'
    })


@staff_member_required
def dashboard_employee_toggle(request, pk):
    """Toggle an employee's active status."""
    user = get_object_or_404(User, pk=pk, is_staff=True)
    if request.method == 'POST':
        if user == request.user:
            messages.error(request, 'You cannot deactivate yourself.')
        else:
            user.is_active = not user.is_active
            user.save()
            status = 'activated' if user.is_active else 'deactivated'
            messages.success(request, f'Employee "{user.get_full_name()}" has been {status}.')
    return redirect('dashboard_employees')


# ─── Attempt Management ─────────────────────────────────────

@staff_member_required
def dashboard_attempts(request):
    """View all quiz attempts."""
    attempts = (
        QuizAttempt.objects
        .select_related('user', 'quiz', 'quiz__department')
        .order_by('-started_at')[:100]
    )
    context = {'attempts': attempts, 'active_page': 'attempts'}
    return render(request, 'quizzes/dashboard/attempts.html', context)


# ─── All Questions Management ────────────────────────────────

@staff_member_required
def dashboard_all_questions(request):
    """Paginated list of ALL questions across all quizzes."""
    quiz_id = request.GET.get('quiz')
    search = request.GET.get('q', '').strip()

    questions = Question.objects.select_related('quiz', 'quiz__department').prefetch_related('choices')

    if quiz_id:
        questions = questions.filter(quiz_id=quiz_id)
    if search:
        questions = questions.filter(text__icontains=search)

    questions = questions.order_by('quiz__name', 'order', 'id')
    paginator = Paginator(questions, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    quizzes = Quiz.objects.order_by('name')

    context = {
        'page_obj': page_obj,
        'quizzes': quizzes,
        'selected_quiz': int(quiz_id) if quiz_id else None,
        'search_query': search,
        'active_page': 'questions',
        'total_questions': paginator.count,
    }
    return render(request, 'quizzes/dashboard/all_questions.html', context)


@staff_member_required
def dashboard_edit_question(request, pk):
    """Edit a single question and its choices."""
    question = get_object_or_404(Question.objects.prefetch_related('choices'), pk=pk)
    choices = list(question.choices.all())

    # Map existing choices to a/b/c/d labels by position
    choice_map = {}
    labels = ['a', 'b', 'c', 'd']
    current_correct = None
    for idx, choice in enumerate(choices):
        if idx < 4:
            choice_map[labels[idx]] = choice
            if choice.is_correct:
                current_correct = labels[idx]

    if request.method == 'POST':
        form = QuestionEditForm(request.POST)
        if form.is_valid():
            question.text = form.cleaned_data['question_text']
            question.save()

            correct = form.cleaned_data['correct_answer']

            for label in labels:
                text = form.cleaned_data.get(f'choice_{label}', '').strip()
                if label in choice_map:
                    # Update existing choice
                    ch = choice_map[label]
                    if text:
                        ch.text = text
                        ch.is_correct = (label == correct)
                        ch.save()
                    else:
                        ch.delete()
                elif text:
                    # Create new choice
                    Choice.objects.create(
                        question=question,
                        text=text,
                        is_correct=(label == correct)
                    )

            messages.success(request, f'Question #{question.order} updated successfully!')
            # Redirect back to same page with filters preserved
            next_url = request.GET.get('next', '')
            if next_url:
                return redirect(next_url)
            return redirect('dashboard_all_questions')
    else:
        form = QuestionEditForm(initial={
            'question_text': question.text,
            'choice_a': choice_map.get('a', Choice()).text if 'a' in choice_map else '',
            'choice_b': choice_map.get('b', Choice()).text if 'b' in choice_map else '',
            'choice_c': choice_map.get('c', Choice()).text if 'c' in choice_map else '',
            'choice_d': choice_map.get('d', Choice()).text if 'd' in choice_map else '',
            'correct_answer': current_correct or 'a',
        })

    context = {
        'form': form,
        'question': question,
        'active_page': 'questions',
    }
    return render(request, 'quizzes/dashboard/edit_question.html', context)


# ═══════════════════════════════════════════════════════════════
# PACKAGES
# ═══════════════════════════════════════════════════════════════

# ─── Public Package Views ────────────────────────────────────

def packages_list(request):
    """List all active packages."""
    packages = Package.objects.filter(is_active=True, status='approved')

    # Annotate enrollment status for authenticated users
    if request.user.is_authenticated:
        user_purchases = set(
            PackagePurchase.objects.filter(
                user=request.user, payment_status='completed'
            ).values_list('package_id', flat=True)
        )
        for pkg in packages:
            pkg.is_enrolled = pkg.id in user_purchases
    else:
        for pkg in packages:
            pkg.is_enrolled = False

    context = {
        'packages': packages,
        'total_packages': packages.count(),
    }
    return render(request, 'quizzes/packages_list.html', context)


def package_detail(request, slug):
    """Show package details and included quizzes."""
    package = get_object_or_404(Package, slug=slug, is_active=True, status='approved')
    quizzes = package.quizzes.filter(is_published=True).select_related('department')

    is_enrolled = False
    if request.user.is_authenticated:
        is_enrolled = PackagePurchase.objects.filter(
            user=request.user, package=package, payment_status='completed'
        ).exists()

        # Add user attempt data to each quiz
        if is_enrolled:
            for quiz in quizzes:
                quiz.user_attempts = QuizAttempt.objects.filter(
                    user=request.user, quiz=quiz
                ).count()
                best = QuizAttempt.objects.filter(
                    user=request.user, quiz=quiz
                ).order_by('-score').first()
                quiz.best_score = best.score if best else None
                quiz.user_passed = best.passed if best else False

    enrollment_count = package.enrollment_count

    context = {
        'package': package,
        'quizzes': quizzes,
        'is_enrolled': is_enrolled,
        'enrollment_count': enrollment_count,
    }
    return render(request, 'quizzes/package_detail.html', context)


@login_required
def package_purchase(request, slug):
    """Initiate package purchase — free packages are enrolled instantly,
    paid packages redirect to SSLCommerz payment gateway."""
    package = get_object_or_404(Package, slug=slug, is_active=True)

    if request.method != 'POST':
        return redirect('package_detail', slug=slug)

    # Check if already enrolled with a completed payment
    existing = PackagePurchase.objects.filter(
        user=request.user, package=package, payment_status='completed'
    ).first()
    if existing:
        messages.info(request, 'You are already enrolled in this package.')
        return redirect('package_detail', slug=slug)

    effective_price = package.effective_price

    # ── FREE PACKAGE: Instant enrollment ──
    if effective_price == 0:
        # Remove any old pending records
        PackagePurchase.objects.filter(
            user=request.user, package=package
        ).exclude(payment_status='completed').delete()

        purchase = PackagePurchase.objects.create(
            user=request.user,
            package=package,
            transaction_id=f'FREE-{uuid.uuid4().hex[:12].upper()}',
            payment_status='completed',
            amount_paid=0,
            payment_method='free',
        )
        record_vendor_sale(purchase=purchase, sale_type='package')
        messages.success(
            request,
            f'🎉 You have successfully enrolled in "{package.name}"! '
            f'You now have access to all {package.quiz_count} quizzes.'
        )
        return redirect('package_detail', slug=slug)

    # ── PAID PACKAGE: Initiate SSLCommerz payment ──
    tran_id = f'PKG-{uuid.uuid4().hex[:12].upper()}'

    # Remove old pending records and create a fresh one
    PackagePurchase.objects.filter(
        user=request.user, package=package
    ).exclude(payment_status='completed').delete()

    purchase = PackagePurchase.objects.create(
        user=request.user,
        package=package,
        transaction_id=tran_id,
        payment_status='pending',
        amount_paid=effective_price,
    )

    base_url = django_settings.SSLCOMMERZ_BASE_URL

    post_body = {
        'total_amount': str(effective_price),
        'currency': 'BDT',
        'tran_id': tran_id,
        'success_url': f'{base_url}/payment/success/',
        'fail_url': f'{base_url}/payment/fail/',
        'cancel_url': f'{base_url}/payment/cancel/',
        'ipn_url': f'{base_url}/payment/ipn/',
        'cus_name': request.user.get_full_name() or request.user.username,
        'cus_email': request.user.email or 'customer@example.com',
        'cus_phone': '01700000000',
        'cus_add1': 'N/A',
        'cus_city': 'Dhaka',
        'cus_country': 'Bangladesh',
        'product_name': package.name,
        'product_category': 'Quiz Package',
        'product_profile': 'non-physical-goods',
        'shipping_method': 'NO',
        'num_of_item': str(package.quiz_count),
        # Pass type:slug and user ID as custom values for callback
        'value_a': f'package:{slug}',
        'value_b': str(request.user.id),
    }

    try:
        from sslcommerz_lib import SSLCOMMERZ

        sslcz_settings = {
            'store_id': django_settings.SSLCOMMERZ_STORE_ID,
            'store_pass': django_settings.SSLCOMMERZ_STORE_PASSWORD,
            'issandbox': django_settings.SSLCOMMERZ_IS_SANDBOX,
        }
        sslcz = SSLCOMMERZ(sslcz_settings)
        response = sslcz.createSession(post_body)

        if response.get('status') == 'SUCCESS':
            gateway_url = response.get('GatewayPageURL')
            if gateway_url:
                return redirect(gateway_url)

        # SSLCommerz returned an error
        logger.error(f'SSLCommerz session creation failed: {response}')
        purchase.payment_status = 'failed'
        purchase.save()
        messages.error(
            request,
            'Payment gateway error. Please try again later or contact support.'
        )

    except ImportError:
        # sslcommerz_lib is not installed — show a helpful message
        logger.warning('sslcommerz_lib not installed. Payment gateway unavailable.')
        purchase.payment_status = 'failed'
        purchase.save()
        messages.warning(
            request,
            '⚠️ Payment gateway is not configured yet. '
            'Please install sslcommerz-lib and add your store credentials in settings.py. '
            'Run: pip install sslcommerz-lib'
        )

    except Exception as e:
        logger.error(f'SSLCommerz error: {e}')
        purchase.payment_status = 'failed'
        purchase.save()
        messages.error(
            request,
            'An unexpected error occurred with the payment gateway. Please try again.'
        )

    return redirect('package_detail', slug=slug)


@login_required
def quiz_purchase(request, slug):
    """Initiate an individual quiz purchase — free quizzes are granted instantly,
    paid quizzes redirect to the SSLCommerz payment gateway."""
    quiz = get_object_or_404(Quiz, slug=slug, is_published=True)

    if request.method != 'POST':
        return redirect('quiz_detail', slug=slug)

    if not quiz.is_paid:
        messages.info(request, 'This quiz is free — you can take it directly.')
        return redirect('quiz_detail', slug=slug)

    existing = QuizPurchase.objects.filter(
        user=request.user, quiz=quiz, payment_status='completed'
    ).first()
    if existing:
        messages.info(request, 'You already own this quiz.')
        return redirect('quiz_detail', slug=slug)

    price = quiz.price
    tran_id = f'QIZ-{uuid.uuid4().hex[:12].upper()}'

    QuizPurchase.objects.filter(
        user=request.user, quiz=quiz
    ).exclude(payment_status='completed').delete()

    purchase = QuizPurchase.objects.create(
        user=request.user,
        quiz=quiz,
        transaction_id=tran_id,
        payment_status='pending',
        amount_paid=price,
    )

    base_url = django_settings.SSLCOMMERZ_BASE_URL

    post_body = {
        'total_amount': str(price),
        'currency': 'BDT',
        'tran_id': tran_id,
        'success_url': f'{base_url}/payment/success/',
        'fail_url': f'{base_url}/payment/fail/',
        'cancel_url': f'{base_url}/payment/cancel/',
        'ipn_url': f'{base_url}/payment/ipn/',
        'cus_name': request.user.get_full_name() or request.user.username,
        'cus_email': request.user.email or 'customer@example.com',
        'cus_phone': '01700000000',
        'cus_add1': 'N/A',
        'cus_city': 'Dhaka',
        'cus_country': 'Bangladesh',
        'product_name': quiz.name,
        'product_category': 'Quiz',
        'product_profile': 'non-physical-goods',
        'shipping_method': 'NO',
        'num_of_item': '1',
        'value_a': f'quiz:{slug}',
        'value_b': str(request.user.id),
    }

    try:
        from sslcommerz_lib import SSLCOMMERZ

        sslcz_settings = {
            'store_id': django_settings.SSLCOMMERZ_STORE_ID,
            'store_pass': django_settings.SSLCOMMERZ_STORE_PASSWORD,
            'issandbox': django_settings.SSLCOMMERZ_IS_SANDBOX,
        }
        sslcz = SSLCOMMERZ(sslcz_settings)
        response = sslcz.createSession(post_body)

        if response.get('status') == 'SUCCESS':
            gateway_url = response.get('GatewayPageURL')
            if gateway_url:
                return redirect(gateway_url)

        logger.error(f'SSLCommerz session creation failed: {response}')
        purchase.payment_status = 'failed'
        purchase.save()
        messages.error(request, 'Payment gateway error. Please try again later.')

    except ImportError:
        logger.warning('sslcommerz_lib not installed. Payment gateway unavailable.')
        purchase.payment_status = 'failed'
        purchase.save()
        messages.warning(
            request,
            '⚠️ Payment gateway is not configured yet. '
            'Run: pip install sslcommerz-lib and add your store credentials in settings.py.'
        )

    except Exception as e:
        logger.error(f'SSLCommerz error: {e}')
        purchase.payment_status = 'failed'
        purchase.save()
        messages.error(request, 'An unexpected error occurred with the payment gateway.')

    return redirect('quiz_detail', slug=slug)


# ─── SSLCommerz Payment Callbacks ────────────────────────────

def _resolve_purchase(tran_id):
    """Find a pending/any purchase by transaction id across both quiz and
    package purchases. Returns (purchase, kind) or (None, None)."""
    purchase = PackagePurchase.objects.filter(transaction_id=tran_id).first()
    if purchase:
        return purchase, 'package'
    purchase = QuizPurchase.objects.filter(transaction_id=tran_id).first()
    if purchase:
        return purchase, 'quiz'
    return None, None


def _purchase_redirect(kind, purchase):
    """Redirect target for a given purchase."""
    if kind == 'quiz':
        return redirect('quiz_detail', slug=purchase.quiz.slug)
    return redirect('package_detail', slug=purchase.package.slug)


@csrf_exempt
def payment_success(request):
    """SSLCommerz redirects the user here after a successful payment.
    Handles both individual quiz purchases and package purchases."""
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id', '')
        val_id = request.POST.get('val_id', '')
        status = request.POST.get('status', '')
        card_type = request.POST.get('card_type', '')
        tran_date = request.POST.get('tran_date', '')

        if status == 'VALID' or status == 'VALIDATED':
            purchase, kind = _resolve_purchase(tran_id)
            if purchase is None:
                messages.error(request, 'Transaction not found.')
                return redirect('packages')

            validated = _validate_with_sslcommerz(val_id, tran_id, purchase.amount_paid)
            if validated:
                purchase.payment_status = 'completed'
                purchase.sslcommerz_val_id = val_id
                purchase.sslcommerz_tran_date = tran_date
                purchase.payment_method = card_type
                purchase.save()
                record_vendor_sale(purchase=purchase, sale_type=kind)
                item_name = purchase.quiz.name if kind == 'quiz' else purchase.package.name
                messages.success(
                    request,
                    f'🎉 Payment successful! You now have access to "{item_name}".'
                )
            else:
                messages.warning(
                    request,
                    'Payment received but validation failed. '
                    'Please contact support with your transaction ID: ' + tran_id
                )
            return _purchase_redirect(kind, purchase)

    return redirect('packages')


@csrf_exempt
def payment_fail(request):
    """SSLCommerz redirects the user here after a failed payment."""
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id', '')
        purchase, kind = _resolve_purchase(tran_id)
        if purchase:
            purchase.payment_status = 'failed'
            purchase.save()
            messages.error(request, 'Payment failed. Please try again.')
            return _purchase_redirect(kind, purchase)
        messages.error(request, 'Payment failed. Please try again.')

    return redirect('packages')


@csrf_exempt
def payment_cancel(request):
    """SSLCommerz redirects the user here if they cancel payment."""
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id', '')
        purchase, kind = _resolve_purchase(tran_id)
        if purchase:
            purchase.payment_status = 'cancelled'
            purchase.save()
            messages.info(request, 'Payment was cancelled.')
            return _purchase_redirect(kind, purchase)
        messages.info(request, 'Payment was cancelled.')

    return redirect('packages')


@csrf_exempt
def payment_ipn(request):
    """IPN (Instant Payment Notification) listener.
    SSLCommerz sends a POST here for every payment event.
    This runs asynchronously and may arrive before the user returns."""
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id', '')
        val_id = request.POST.get('val_id', '')
        status = request.POST.get('status', '')
        card_type = request.POST.get('card_type', '')
        tran_date = request.POST.get('tran_date', '')

        purchase, kind = _resolve_purchase(tran_id)
        if purchase is None:
            logger.warning(f'IPN: Transaction {tran_id} not found')
            return HttpResponse('IPN Received', status=200)

        if status == 'VALID' or status == 'VALIDATED':
            validated = _validate_with_sslcommerz(val_id, tran_id, purchase.amount_paid)
            if validated:
                purchase.payment_status = 'completed'
                purchase.sslcommerz_val_id = val_id
                purchase.sslcommerz_tran_date = tran_date
                purchase.payment_method = card_type
                purchase.save()
                record_vendor_sale(purchase=purchase, sale_type=kind)
                logger.info(f'IPN: Payment completed for {tran_id}')
        elif status == 'FAILED':
            purchase.payment_status = 'failed'
            purchase.save()
        elif status == 'CANCELLED':
            purchase.payment_status = 'cancelled'
            purchase.save()

    return HttpResponse('IPN Received', status=200)


def _validate_with_sslcommerz(val_id, tran_id, expected_amount):
    """Validate a transaction with SSLCommerz Order Validation API.
    Returns True if the transaction is valid and amount matches."""
    try:
        from sslcommerz_lib import SSLCOMMERZ

        sslcz_settings = {
            'store_id': django_settings.SSLCOMMERZ_STORE_ID,
            'store_pass': django_settings.SSLCOMMERZ_STORE_PASSWORD,
            'issandbox': django_settings.SSLCOMMERZ_IS_SANDBOX,
        }
        sslcz = SSLCOMMERZ(sslcz_settings)
        response = sslcz.transaction_query_tranid(tran_id)

        if response.get('status') in ('VALID', 'VALIDATED'):
            api_amount = float(response.get('amount', 0))
            if abs(api_amount - float(expected_amount)) < 1:
                return True
            else:
                logger.warning(
                    f'Amount mismatch for {tran_id}: '
                    f'expected {expected_amount}, got {api_amount}'
                )
        return False

    except ImportError:
        # Library not installed — skip validation in development
        logger.warning('sslcommerz_lib not installed, skipping validation')
        return True

    except Exception as e:
        logger.error(f'SSLCommerz validation error: {e}')
        return False


# ─── Dashboard Package Views ────────────────────────────────

@staff_member_required
def dashboard_packages(request):
    """List all packages in the admin dashboard."""
    packages = Package.objects.all().order_by('-created_at')
    context = {'packages': packages, 'active_page': 'packages'}
    return render(request, 'quizzes/dashboard/packages.html', context)


@staff_member_required
def dashboard_package_create(request):
    """Create a new package."""
    if request.method == 'POST':
        form = PackageForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Package "{form.cleaned_data["name"]}" created successfully!')
            return redirect('dashboard_packages')
    else:
        form = PackageForm()
    return render(request, 'quizzes/dashboard/package_form.html', {
        'form': form, 'action': 'Create', 'active_page': 'packages'
    })


@staff_member_required
def dashboard_package_edit(request, pk):
    """Edit an existing package."""
    package = get_object_or_404(Package, pk=pk)
    if request.method == 'POST':
        form = PackageForm(request.POST, instance=package)
        if form.is_valid():
            form.save()
            messages.success(request, f'Package "{package.name}" updated successfully!')
            return redirect('dashboard_packages')
    else:
        form = PackageForm(instance=package)
    return render(request, 'quizzes/dashboard/package_form.html', {
        'form': form, 'action': 'Edit', 'package': package, 'active_page': 'packages'
    })


@staff_member_required
def dashboard_package_delete(request, pk):
    """Delete a package."""
    package = get_object_or_404(Package, pk=pk)
    if request.method == 'POST':
        name = package.name
        package.delete()
        messages.success(request, f'Package "{name}" deleted.')
        return redirect('dashboard_packages')
    return render(request, 'quizzes/dashboard/package_confirm_delete.html', {
        'package': package
    })


# ═══════════════════════════════════════════════════════════════
# NEW FEATURES
# ═══════════════════════════════════════════════════════════════

# ─── Bookmarked Questions ────────────────────────────────────

@login_required
def toggle_bookmark(request):
    """Toggle a bookmark on a question (AJAX)."""
    if request.method == 'POST':
        question_id = request.POST.get('question_id')
        try:
            question = Question.objects.get(id=question_id)
        except Question.DoesNotExist:
            return JsonResponse({'error': 'Question not found'}, status=404)

        bookmark, created = BookmarkedQuestion.objects.get_or_create(
            user=request.user,
            question=question
        )
        if not created:
            bookmark.delete()
            return JsonResponse({'bookmarked': False})
        return JsonResponse({'bookmarked': True})

    return JsonResponse({'error': 'POST required'}, status=400)


@login_required
def bookmarks_list(request):
    """View all bookmarked questions."""
    bookmarks = (
        BookmarkedQuestion.objects
        .filter(user=request.user)
        .select_related('question', 'question__quiz', 'question__quiz__department')
        .order_by('-created_at')
    )

    context = {
        'bookmarks': bookmarks,
        'total_bookmarks': bookmarks.count(),
    }
    return render(request, 'quizzes/bookmarks.html', context)


# ─── CSV / JSON Import ──────────────────────────────────────

def _handle_csv_json_import(request, quiz, redirect_name):
    """Parse and import questions from an uploaded CSV/JSON file into `quiz`.
    Sets flash messages and returns a redirect to `redirect_name` with pk=quiz.pk.
    Shared by the staff and vendor question-management views."""
    import csv
    import json as json_lib
    import io

    if request.method != 'POST':
        return redirect(redirect_name, pk=quiz.pk)

    form = CSVJSONUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return redirect(redirect_name, pk=quiz.pk)

    uploaded_file = request.FILES['file']
    clear_existing = form.cleaned_data.get('clear_existing', False)
    filename = uploaded_file.name.lower()

    try:
        content = uploaded_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        messages.error(request, 'File encoding error. Please upload a UTF-8 encoded file.')
        return redirect(redirect_name, pk=quiz.pk)

    parsed_questions = []

    if filename.endswith('.csv'):
        reader = csv.DictReader(io.StringIO(content))
        for row_num, row in enumerate(reader, 1):
            q_text = row.get('question', '').strip()
            if not q_text:
                continue
            choices = []
            answer = row.get('answer', '').strip().lower()
            for label in ['a', 'b', 'c', 'd']:
                opt = row.get(label, row.get(label.upper(), '')).strip()
                if opt:
                    choices.append({'label': label, 'text': opt})
            explanation = row.get('explanation', '').strip()
            parsed_questions.append({
                'number': row_num,
                'text': q_text,
                'choices': choices,
                'answer': answer,
                'explanation': explanation,
            })

    elif filename.endswith('.json'):
        try:
            data = json_lib.loads(content)
            if isinstance(data, list):
                for idx, item in enumerate(data, 1):
                    choices = []
                    for label in ['a', 'b', 'c', 'd']:
                        opt = item.get(label, item.get(label.upper(), ''))
                        if opt:
                            choices.append({'label': label, 'text': str(opt).strip()})
                    if not choices and 'choices' in item:
                        for ci, ch in enumerate(item['choices'][:4]):
                            label = chr(97 + ci)
                            if isinstance(ch, dict):
                                choices.append({'label': label, 'text': ch.get('text', str(ch))})
                            else:
                                choices.append({'label': label, 'text': str(ch)})
                    parsed_questions.append({
                        'number': item.get('number', idx),
                        'text': item.get('question', item.get('text', '')).strip(),
                        'choices': choices,
                        'answer': str(item.get('answer', '')).strip().lower(),
                        'explanation': item.get('explanation', ''),
                    })
        except json_lib.JSONDecodeError:
            messages.error(request, 'Invalid JSON file. Please check the format.')
            return redirect(redirect_name, pk=quiz.pk)
    else:
        messages.error(request, 'Unsupported file format. Please upload a .csv or .json file.')
        return redirect(redirect_name, pk=quiz.pk)

    if not parsed_questions:
        messages.error(request, 'No questions found in the uploaded file.')
        return redirect(redirect_name, pk=quiz.pk)

    valid_qs, skipped, errors = filter_valid_questions(parsed_questions)
    if not valid_qs:
        messages.error(request, f'No valid questions found. {len(errors)} error(s).')
        return redirect(redirect_name, pk=quiz.pk)

    if clear_existing:
        quiz.questions.all().delete()

    with transaction.atomic():
        count = 0
        for q_data in valid_qs:
            last_order = quiz.questions.order_by('-order').values_list('order', flat=True).first() or 0
            question = Question.objects.create(
                quiz=quiz,
                text=q_data['text'],
                explanation=q_data.get('explanation', ''),
                order=last_order + 1
            )
            for choice_data in q_data['choices']:
                Choice.objects.create(
                    question=question,
                    text=choice_data['text'],
                    is_correct=(choice_data['label'] == q_data.get('answer', ''))
                )
            count += 1

    if skipped:
        messages.warning(
            request,
            f'Imported {count} question(s). Skipped {len(skipped)} malformed question(s).'
        )
    else:
        messages.success(request, f'Successfully imported {count} question(s) from file!')

    return redirect(redirect_name, pk=quiz.pk)


@staff_member_required
def dashboard_import_csv_json(request, pk):
    """Import questions from a CSV or JSON file upload."""
    quiz = get_object_or_404(Quiz, pk=pk)
    return _handle_csv_json_import(request, quiz, 'dashboard_quiz_questions')


# ─── PDF Certificate Generation ─────────────────────────────

@login_required
def download_certificate(request, attempt_id):
    """Generate and download a PDF certificate for a passed quiz attempt."""
    attempt = get_object_or_404(
        QuizAttempt,
        id=attempt_id,
        user=request.user,
        passed=True
    )

    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import inch, cm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas as pdf_canvas
    from reportlab.lib.utils import simpleSplit

    response = HttpResponse(content_type='application/pdf')
    filename = f'certificate_{attempt.quiz.slug}_{attempt.user.username}.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    width, height = landscape(A4)
    c = pdf_canvas.Canvas(response, pagesize=landscape(A4))

    # Background
    c.setFillColor(HexColor('#0f172a'))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Border with gradient effect
    c.setStrokeColor(HexColor('#6366f1'))
    c.setLineWidth(3)
    c.roundRect(30, 30, width - 60, height - 60, 15)

    # Inner border
    c.setStrokeColor(HexColor('#818cf8'))
    c.setLineWidth(1)
    c.roundRect(40, 40, width - 80, height - 80, 12)

    # Title
    c.setFillColor(HexColor('#e2e8f0'))
    c.setFont('Helvetica', 14)
    c.drawCentredString(width / 2, height - 90, '✦  QUIZMASTER  ✦')

    c.setFillColor(HexColor('#6366f1'))
    c.setFont('Helvetica-Bold', 36)
    c.drawCentredString(width / 2, height - 140, 'CERTIFICATE OF ACHIEVEMENT')

    # Decorative line
    c.setStrokeColor(HexColor('#6366f1'))
    c.setLineWidth(2)
    c.line(width / 2 - 150, height - 155, width / 2 + 150, height - 155)

    # Presented to
    c.setFillColor(HexColor('#94a3b8'))
    c.setFont('Helvetica', 14)
    c.drawCentredString(width / 2, height - 195, 'This certificate is proudly presented to')

    # User name
    full_name = f'{attempt.user.first_name} {attempt.user.last_name}'.strip()
    if not full_name:
        full_name = attempt.user.username
    c.setFillColor(HexColor('#f8fafc'))
    c.setFont('Helvetica-Bold', 32)
    c.drawCentredString(width / 2, height - 240, full_name)

    # Line under name
    c.setStrokeColor(HexColor('#334155'))
    c.setLineWidth(0.5)
    c.line(width / 2 - 180, height - 250, width / 2 + 180, height - 250)

    # Achievement text
    c.setFillColor(HexColor('#94a3b8'))
    c.setFont('Helvetica', 13)
    c.drawCentredString(width / 2, height - 280, f'for successfully completing and passing the quiz')

    c.setFillColor(HexColor('#a78bfa'))
    c.setFont('Helvetica-Bold', 20)
    quiz_name = attempt.quiz.name
    if len(quiz_name) > 50:
        quiz_name = quiz_name[:47] + '...'
    c.drawCentredString(width / 2, height - 310, f'"{quiz_name}"')

    c.setFillColor(HexColor('#94a3b8'))
    c.setFont('Helvetica', 13)
    c.drawCentredString(
        width / 2, height - 340,
        f'in the {attempt.quiz.department.name} department'
    )

    # Score info
    c.setFillColor(HexColor('#e2e8f0'))
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(
        width / 2, height - 380,
        f'Score: {attempt.score}/{attempt.total_marks}  •  {attempt.percentage}%'
    )

    # Tier label
    pct = float(attempt.percentage)
    if pct >= 90:
        tier = 'Expert Level'
        tier_color = '#22c55e'
    elif pct >= 70:
        tier = 'Advanced Level'
        tier_color = '#6366f1'
    elif pct >= 50:
        tier = 'Intermediate Level'
        tier_color = '#eab308'
    else:
        tier = 'Beginner Level'
        tier_color = '#94a3b8'

    c.setFillColor(HexColor(tier_color))
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(width / 2, height - 405, f'★  {tier}  ★')

    # Date and ID
    date_str = attempt.completed_at.strftime('%B %d, %Y') if attempt.completed_at else 'N/A'
    c.setFillColor(HexColor('#64748b'))
    c.setFont('Helvetica', 10)
    c.drawCentredString(width / 2, 75, f'Date: {date_str}  |  Certificate ID: {str(attempt.id)[:8].upper()}')

    c.setFont('Helvetica', 9)
    c.drawCentredString(width / 2, 55, 'This certificate was automatically generated by QuizMaster.')

    c.save()
    return response


# ─── Profile with Analytics Data ─────────────────────────────

@login_required
def profile(request):
    """User profile with quiz history and analytics chart data."""
    attempts = QuizAttempt.objects.filter(
        user=request.user
    ).select_related('quiz', 'quiz__department').order_by('-started_at')

    total_attempts = attempts.count()
    passed_count = attempts.filter(passed=True).count()
    failed_count = total_attempts - passed_count

    # Chart data: scores over time (last 20 attempts, chronological)
    chart_attempts = list(attempts[:20])
    chart_attempts.reverse()
    chart_labels = []
    chart_scores = []
    for a in chart_attempts:
        chart_labels.append(a.started_at.strftime('%b %d'))
        chart_scores.append(float(a.percentage))

    # Department performance data
    dept_stats = {}
    for a in attempts:
        dept = a.quiz.department.name
        if dept not in dept_stats:
            dept_stats[dept] = {'total': 0, 'passed': 0}
        dept_stats[dept]['total'] += 1
        if a.passed:
            dept_stats[dept]['passed'] += 1

    dept_labels = list(dept_stats.keys())
    dept_pass_rates = [
        round((v['passed'] / v['total']) * 100, 1) if v['total'] > 0 else 0
        for v in dept_stats.values()
    ]

    # Bookmarks count
    bookmarks_count = BookmarkedQuestion.objects.filter(user=request.user).count()

    import json as json_lib
    context = {
        'attempts': attempts[:20],
        'total_attempts': total_attempts,
        'passed_count': passed_count,
        'failed_count': failed_count,
        'pass_rate': round((passed_count / total_attempts) * 100, 1) if total_attempts > 0 else 0,
        'bookmarks_count': bookmarks_count,
        # Chart data as JSON strings
        'chart_labels': json_lib.dumps(chart_labels),
        'chart_scores': json_lib.dumps(chart_scores),
        'dept_labels': json_lib.dumps(dept_labels),
        'dept_pass_rates': json_lib.dumps(dept_pass_rates),
        'passed_count_json': passed_count,
        'failed_count_json': failed_count,
    }
    return render(request, 'quizzes/profile.html', context)


# ═══════════════════════════════════════════════════════════════
# VENDOR MARKETPLACE
# ═══════════════════════════════════════════════════════════════

# ─── Shared import helper (used by vendor question management) ──

def _import_gdoc_to_quiz(quiz, doc_url, clear_existing, user):
    """Import questions from a Google Doc into a quiz.
    Returns (level, message) where level is 'success' | 'warning' | 'error'."""
    upload = GoogleDocUpload.objects.create(
        quiz=quiz, doc_url=doc_url, uploaded_by=user, status='processing'
    )
    content, error = fetch_doc_content(doc_url)
    if error:
        upload.status = 'failed'
        upload.error_message = error
        upload.save()
        return 'error', f'Failed to fetch document: {error}'

    all_parsed = parse_questions(content)
    if not all_parsed:
        upload.status = 'failed'
        upload.error_message = 'No questions could be parsed from the document.'
        upload.save()
        return 'error', 'No questions could be parsed. Check the document format.'

    valid_parsed, skipped_nums, skip_errors = filter_valid_questions(all_parsed)
    if not valid_parsed:
        upload.status = 'failed'
        upload.error_message = '\n'.join(skip_errors)
        upload.save()
        return 'error', f'No valid questions found. {len(skip_errors)} error(s) detected.'

    if clear_existing:
        quiz.questions.all().delete()

    with transaction.atomic():
        count = import_questions_to_quiz(quiz, valid_parsed)
        upload.status = 'success'
        upload.questions_imported = count
        upload.save()

    if skipped_nums:
        return 'warning', (
            f'Imported {count} question(s). '
            f'Skipped {len(skipped_nums)} malformed question(s): {skipped_nums[:10]}.'
        )
    return 'success', f'Successfully imported {count} question(s) from Google Docs!'


# ─── Vendor Registration & Onboarding ───────────────────────

def vendor_register(request):
    """Dedicated vendor registration. Creates a pending VendorProfile."""
    if request.user.is_authenticated:
        profile = get_vendor_profile(request.user)
        if profile:
            return redirect('vendor_dashboard' if profile.is_approved else 'vendor_pending')

    if request.method == 'POST':
        form = VendorRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                'Your vendor application has been submitted! An admin will review '
                'it shortly. You will get access once approved.'
            )
            return redirect('vendor_pending')
    else:
        form = VendorRegisterForm()

    return render(request, 'quizzes/vendor/register.html', {'form': form})


@login_required
def vendor_pending(request):
    """Status page shown to vendors who are not yet approved."""
    profile = get_vendor_profile(request.user)
    if profile is None:
        return redirect('vendor_register')
    if profile.is_approved:
        return redirect('vendor_dashboard')
    return render(request, 'quizzes/vendor/pending.html', {'profile': profile})


# ─── Vendor Dashboard ───────────────────────────────────────

@vendor_required
def vendor_dashboard(request, profile):
    """Vendor overview: content + sales + earnings."""
    quizzes = Quiz.objects.filter(owner=request.user)
    packages = Package.objects.filter(owner=request.user)
    sales = VendorSale.objects.filter(vendor=request.user)

    context = {
        'profile': profile,
        'active_page': 'overview',
        'total_quizzes': quizzes.count(),
        'published_quizzes': quizzes.filter(is_published=True).count(),
        'pending_quizzes': quizzes.filter(status='pending').count(),
        'total_packages': packages.count(),
        'fee_per_sale': PlatformSetting.load().vendor_fee_per_sale,
        'total_sales': sales.count(),
        'total_earnings': profile.total_earnings,
        'total_fees': profile.total_fees,
        'recent_sales': sales.select_related('quiz', 'package', 'buyer')[:8],
        'recent_quizzes': quizzes.order_by('-created_at')[:6],
    }
    return render(request, 'quizzes/vendor/index.html', context)


# ─── Vendor Quizzes ─────────────────────────────────────────

def _get_owned_quiz(request, pk):
    return get_object_or_404(Quiz, pk=pk, owner=request.user)


@vendor_required
def vendor_quizzes(request, profile):
    quizzes = Quiz.objects.filter(owner=request.user).select_related(
        'department', 'subcategory'
    ).order_by('-created_at')
    return render(request, 'quizzes/vendor/quizzes.html', {
        'quizzes': quizzes, 'active_page': 'quizzes', 'profile': profile,
    })


@vendor_required
def vendor_quiz_create(request, profile):
    if request.method == 'POST':
        form = VendorQuizForm(request.POST, vendor=request.user)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.owner = request.user
            quiz.status = 'draft'
            quiz.is_published = False
            quiz.save()
            messages.success(request, f'Quiz "{quiz.name}" created as a draft. Add questions, then submit for review.')
            return redirect('vendor_quiz_questions', pk=quiz.pk)
    else:
        form = VendorQuizForm(vendor=request.user)
    return render(request, 'quizzes/vendor/quiz_form.html', {
        'form': form, 'action': 'Create', 'active_page': 'quizzes', 'profile': profile,
    })


@vendor_required
def vendor_quiz_edit(request, profile, pk):
    quiz = _get_owned_quiz(request, pk)
    if request.method == 'POST':
        form = VendorQuizForm(request.POST, instance=quiz, vendor=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Quiz "{quiz.name}" updated.')
            return redirect('vendor_quizzes')
    else:
        form = VendorQuizForm(instance=quiz, vendor=request.user)
    return render(request, 'quizzes/vendor/quiz_form.html', {
        'form': form, 'action': 'Edit', 'quiz': quiz, 'active_page': 'quizzes', 'profile': profile,
    })


@vendor_required
def vendor_quiz_delete(request, profile, pk):
    quiz = _get_owned_quiz(request, pk)
    if request.method == 'POST':
        name = quiz.name
        quiz.delete()
        messages.success(request, f'Quiz "{name}" deleted.')
    return redirect('vendor_quizzes')


@vendor_required
def vendor_quiz_submit(request, profile, pk):
    """Submit a draft/rejected quiz for admin review."""
    quiz = _get_owned_quiz(request, pk)
    if request.method == 'POST':
        if not quiz.has_enough_questions:
            messages.error(
                request,
                f'Add at least {quiz.total_questions} questions before submitting '
                f'(currently {quiz.question_count}).'
            )
            return redirect('vendor_quiz_questions', pk=pk)
        quiz.status = 'pending'
        quiz.submitted_at = timezone.now()
        quiz.rejection_reason = ''
        quiz.save(update_fields=['status', 'submitted_at', 'rejection_reason'])
        messages.success(request, f'"{quiz.name}" submitted for review. An admin will approve or reject it.')
    return redirect('vendor_quizzes')


# ─── Vendor Question Management ─────────────────────────────

@vendor_required
def vendor_quiz_questions(request, profile, pk):
    quiz = _get_owned_quiz(request, pk)
    questions = quiz.questions.prefetch_related('choices').all()
    context = {
        'quiz': quiz,
        'questions': questions,
        'manual_form': ManualQuestionForm(),
        'gdoc_form': GoogleDocUploadForm(),
        'csv_form': CSVJSONUploadForm(),
        'uploads': GoogleDocUpload.objects.filter(quiz=quiz)[:5],
        'active_page': 'quizzes',
        'profile': profile,
    }
    return render(request, 'quizzes/vendor/quiz_questions.html', context)


@vendor_required
def vendor_add_question_manual(request, profile, pk):
    quiz = _get_owned_quiz(request, pk)
    if request.method == 'POST':
        form = ManualQuestionForm(request.POST)
        if form.is_valid():
            last_order = quiz.questions.order_by('-order').values_list('order', flat=True).first() or 0
            question = Question.objects.create(
                quiz=quiz, text=form.cleaned_data['question_text'], order=last_order + 1
            )
            correct = form.cleaned_data['correct_answer']
            for label_key in ['a', 'b', 'c', 'd']:
                text = form.cleaned_data.get(f'choice_{label_key}', '').strip()
                if text:
                    Choice.objects.create(
                        question=question, text=text, is_correct=(label_key == correct)
                    )
            messages.success(request, 'Question added successfully!')
        else:
            messages.error(request, 'Please fix the errors and try again.')
    return redirect('vendor_quiz_questions', pk=pk)


@vendor_required
def vendor_import_gdoc(request, profile, pk):
    quiz = _get_owned_quiz(request, pk)
    if request.method == 'POST':
        form = GoogleDocUploadForm(request.POST)
        if form.is_valid():
            level, message = _import_gdoc_to_quiz(
                quiz, form.cleaned_data['doc_url'],
                form.cleaned_data['clear_existing'], request.user
            )
            getattr(messages, level)(request, message)
    return redirect('vendor_quiz_questions', pk=pk)


@vendor_required
def vendor_import_file(request, profile, pk):
    """Import questions from a CSV/JSON upload (vendor-scoped)."""
    quiz = _get_owned_quiz(request, pk)
    if request.method == 'POST':
        # Reuse the staff CSV/JSON importer by temporarily delegating: the parsing
        # logic is identical, so call the shared importer body inline.
        return _handle_csv_json_import(request, quiz, redirect_name='vendor_quiz_questions')
    return redirect('vendor_quiz_questions', pk=pk)


@vendor_required
def vendor_edit_question(request, profile, pk):
    question = get_object_or_404(Question, pk=pk, quiz__owner=request.user)
    quiz_pk = question.quiz.pk
    choices = list(question.choices.all())
    labels = ['a', 'b', 'c', 'd']
    choice_map = {}
    current_correct = None
    for idx, choice in enumerate(choices):
        if idx < 4:
            choice_map[labels[idx]] = choice
            if choice.is_correct:
                current_correct = labels[idx]

    if request.method == 'POST':
        form = QuestionEditForm(request.POST)
        if form.is_valid():
            question.text = form.cleaned_data['question_text']
            question.explanation = form.cleaned_data.get('explanation', '')
            question.save()
            correct = form.cleaned_data['correct_answer']
            for label in labels:
                text = form.cleaned_data.get(f'choice_{label}', '').strip()
                if label in choice_map:
                    ch = choice_map[label]
                    if text:
                        ch.text = text
                        ch.is_correct = (label == correct)
                        ch.save()
                    else:
                        ch.delete()
                elif text:
                    Choice.objects.create(question=question, text=text, is_correct=(label == correct))
            messages.success(request, 'Question updated.')
            return redirect('vendor_quiz_questions', pk=quiz_pk)
    else:
        form = QuestionEditForm(initial={
            'question_text': question.text,
            'explanation': question.explanation,
            'choice_a': choice_map.get('a').text if 'a' in choice_map else '',
            'choice_b': choice_map.get('b').text if 'b' in choice_map else '',
            'choice_c': choice_map.get('c').text if 'c' in choice_map else '',
            'choice_d': choice_map.get('d').text if 'd' in choice_map else '',
            'correct_answer': current_correct or 'a',
        })
    return render(request, 'quizzes/vendor/edit_question.html', {
        'form': form, 'question': question, 'active_page': 'quizzes', 'profile': profile,
    })


@vendor_required
def vendor_delete_question(request, profile, pk):
    question = get_object_or_404(Question, pk=pk, quiz__owner=request.user)
    quiz_pk = question.quiz.pk
    if request.method == 'POST':
        question.delete()
        messages.success(request, 'Question deleted.')
    return redirect('vendor_quiz_questions', pk=quiz_pk)


# ─── Vendor Categories ──────────────────────────────────────

@vendor_required
def vendor_categories(request, profile):
    """List the vendor's own categories/subcategories and let them propose new ones."""
    my_departments = Department.objects.filter(created_by=request.user).order_by('name')
    my_subcategories = SubCategory.objects.filter(created_by=request.user).select_related('department')
    return render(request, 'quizzes/vendor/categories.html', {
        'my_departments': my_departments,
        'my_subcategories': my_subcategories,
        'active_page': 'categories',
        'profile': profile,
    })


@vendor_required
def vendor_category_create(request, profile):
    if request.method == 'POST':
        form = VendorCategoryForm(request.POST)
        if form.is_valid():
            dept = form.save(commit=False)
            dept.created_by = request.user
            dept.is_approved = False
            dept.is_active = True
            dept.save()
            messages.success(request, f'Category "{dept.name}" submitted for admin approval.')
            return redirect('vendor_categories')
    else:
        form = VendorCategoryForm()
    return render(request, 'quizzes/vendor/category_form.html', {
        'form': form, 'kind': 'Category', 'active_page': 'categories', 'profile': profile,
    })


@vendor_required
def vendor_subcategory_create(request, profile):
    if request.method == 'POST':
        form = SubCategoryForm(request.POST, vendor=request.user)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.created_by = request.user
            sub.is_approved = False
            sub.is_active = True
            sub.save()
            messages.success(request, f'Subcategory "{sub.name}" submitted for admin approval.')
            return redirect('vendor_categories')
    else:
        form = SubCategoryForm(vendor=request.user)
    return render(request, 'quizzes/vendor/category_form.html', {
        'form': form, 'kind': 'Subcategory', 'active_page': 'categories', 'profile': profile,
    })


# ─── Vendor Packages ────────────────────────────────────────

@vendor_required
def vendor_packages(request, profile):
    packages = Package.objects.filter(owner=request.user).order_by('-created_at')
    return render(request, 'quizzes/vendor/packages.html', {
        'packages': packages, 'active_page': 'packages', 'profile': profile,
    })


@vendor_required
def vendor_package_create(request, profile):
    if request.method == 'POST':
        form = VendorPackageForm(request.POST, vendor=request.user)
        if form.is_valid():
            package = form.save(commit=False)
            package.owner = request.user
            package.status = 'draft'
            package.is_active = True
            package.save()
            form.save_m2m()
            messages.success(request, f'Package "{package.name}" created as a draft.')
            return redirect('vendor_packages')
    else:
        form = VendorPackageForm(vendor=request.user)
    return render(request, 'quizzes/vendor/package_form.html', {
        'form': form, 'action': 'Create', 'active_page': 'packages', 'profile': profile,
    })


@vendor_required
def vendor_package_edit(request, profile, pk):
    package = get_object_or_404(Package, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = VendorPackageForm(request.POST, instance=package, vendor=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Package "{package.name}" updated.')
            return redirect('vendor_packages')
    else:
        form = VendorPackageForm(instance=package, vendor=request.user)
    return render(request, 'quizzes/vendor/package_form.html', {
        'form': form, 'action': 'Edit', 'package': package, 'active_page': 'packages', 'profile': profile,
    })


@vendor_required
def vendor_package_delete(request, profile, pk):
    package = get_object_or_404(Package, pk=pk, owner=request.user)
    if request.method == 'POST':
        name = package.name
        package.delete()
        messages.success(request, f'Package "{name}" deleted.')
    return redirect('vendor_packages')


@vendor_required
def vendor_package_submit(request, profile, pk):
    package = get_object_or_404(Package, pk=pk, owner=request.user)
    if request.method == 'POST':
        if not package.quizzes.filter(is_published=True).exists():
            messages.error(request, 'Add at least one published quiz before submitting.')
            return redirect('vendor_packages')
        package.status = 'pending'
        package.submitted_at = timezone.now()
        package.rejection_reason = ''
        package.save(update_fields=['status', 'submitted_at', 'rejection_reason'])
        messages.success(request, f'Package "{package.name}" submitted for review.')
    return redirect('vendor_packages')


# ─── Vendor Sales & Earnings ────────────────────────────────

@vendor_required
def vendor_sales(request, profile):
    sales = VendorSale.objects.filter(vendor=request.user).select_related(
        'quiz', 'package', 'buyer'
    )
    return render(request, 'quizzes/vendor/sales.html', {
        'sales': sales,
        'total_sales': sales.count(),
        'total_earnings': profile.total_earnings,
        'total_fees': profile.total_fees,
        'fee_per_sale': PlatformSetting.load().vendor_fee_per_sale,
        'active_page': 'sales',
        'profile': profile,
    })


# ═══════════════════════════════════════════════════════════════
# ADMIN: VENDOR MARKETPLACE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@staff_member_required
def dashboard_vendors(request):
    status = request.GET.get('status', '')
    vendors = VendorProfile.objects.select_related('user').all()
    if status:
        vendors = vendors.filter(status=status)
    context = {
        'vendors': vendors,
        'status_filter': status,
        'pending_count': VendorProfile.objects.filter(status='pending').count(),
        'active_page': 'vendors',
    }
    return render(request, 'quizzes/dashboard/vendors.html', context)


@staff_member_required
def dashboard_vendor_action(request, pk):
    """Approve / reject / suspend a vendor."""
    vendor = get_object_or_404(VendorProfile, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            vendor.status = 'approved'
            vendor.approved_at = timezone.now()
            vendor.approved_by = request.user
            vendor.rejection_reason = ''
            vendor.save()
            messages.success(request, f'Vendor "{vendor.store_name}" approved.')
        elif action == 'reject':
            vendor.status = 'rejected'
            vendor.rejection_reason = request.POST.get('reason', '')
            vendor.save()
            messages.warning(request, f'Vendor "{vendor.store_name}" rejected.')
        elif action == 'suspend':
            vendor.status = 'suspended'
            vendor.save()
            messages.warning(request, f'Vendor "{vendor.store_name}" suspended.')
    return redirect('dashboard_vendors')


@staff_member_required
def dashboard_review_quizzes(request):
    quizzes = Quiz.objects.filter(status='pending').select_related(
        'department', 'subcategory', 'owner'
    ).order_by('submitted_at')
    return render(request, 'quizzes/dashboard/review_quizzes.html', {
        'quizzes': quizzes, 'active_page': 'reviews',
    })


@staff_member_required
def dashboard_review_quiz_action(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            quiz.status = 'approved'
            quiz.is_published = True
            quiz.reviewed_at = timezone.now()
            quiz.reviewed_by = request.user
            quiz.rejection_reason = ''
            quiz.save()
            messages.success(request, f'Quiz "{quiz.name}" approved and published.')
        elif action == 'reject':
            quiz.status = 'rejected'
            quiz.is_published = False
            quiz.reviewed_at = timezone.now()
            quiz.reviewed_by = request.user
            quiz.rejection_reason = request.POST.get('reason', '')
            quiz.save()
            messages.warning(request, f'Quiz "{quiz.name}" rejected.')
    return redirect('dashboard_review_quizzes')


@staff_member_required
def dashboard_review_packages(request):
    packages = Package.objects.filter(status='pending').select_related('owner').order_by('submitted_at')
    return render(request, 'quizzes/dashboard/review_packages.html', {
        'packages': packages, 'active_page': 'reviews',
    })


@staff_member_required
def dashboard_review_package_action(request, pk):
    package = get_object_or_404(Package, pk=pk)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            package.status = 'approved'
            package.is_active = True
            package.reviewed_at = timezone.now()
            package.reviewed_by = request.user
            package.rejection_reason = ''
            package.save()
            messages.success(request, f'Package "{package.name}" approved.')
        elif action == 'reject':
            package.status = 'rejected'
            package.reviewed_at = timezone.now()
            package.reviewed_by = request.user
            package.rejection_reason = request.POST.get('reason', '')
            package.save()
            messages.warning(request, f'Package "{package.name}" rejected.')
    return redirect('dashboard_review_packages')


@staff_member_required
def dashboard_review_categories(request):
    departments = Department.objects.filter(is_approved=False).select_related('created_by').order_by('created_at')
    subcategories = SubCategory.objects.filter(is_approved=False).select_related('department', 'created_by').order_by('created_at')
    return render(request, 'quizzes/dashboard/review_categories.html', {
        'departments': departments, 'subcategories': subcategories, 'active_page': 'reviews',
    })


@staff_member_required
def dashboard_approve_category(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        if request.POST.get('action') == 'approve':
            department.is_approved = True
            department.save(update_fields=['is_approved'])
            messages.success(request, f'Category "{department.name}" approved.')
        else:
            department.delete()
            messages.warning(request, 'Category rejected and removed.')
    return redirect('dashboard_review_categories')


@staff_member_required
def dashboard_approve_subcategory(request, pk):
    sub = get_object_or_404(SubCategory, pk=pk)
    if request.method == 'POST':
        if request.POST.get('action') == 'approve':
            sub.is_approved = True
            sub.save(update_fields=['is_approved'])
            messages.success(request, f'Subcategory "{sub.name}" approved.')
        else:
            sub.delete()
            messages.warning(request, 'Subcategory rejected and removed.')
    return redirect('dashboard_review_categories')


@staff_member_required
def dashboard_settings(request):
    setting = PlatformSetting.load()
    if request.method == 'POST':
        form = PlatformSettingForm(request.POST, instance=setting)
        if form.is_valid():
            form.save()
            messages.success(request, 'Platform settings updated.')
            return redirect('dashboard_settings')
    else:
        form = PlatformSettingForm(instance=setting)
    return render(request, 'quizzes/dashboard/settings.html', {
        'form': form, 'setting': setting, 'active_page': 'settings',
    })


@staff_member_required
def dashboard_vendor_sales(request):
    sales = VendorSale.objects.select_related('vendor', 'buyer', 'quiz', 'package').all()
    totals = sales.aggregate(
        gross=Sum('sale_amount'),
        fees=Sum('platform_fee'),
        payouts=Sum('vendor_earning'),
    )
    per_vendor = (
        sales.values('vendor__username', 'vendor__id')
        .annotate(
            count=Count('id'),
            gross=Sum('sale_amount'),
            fees=Sum('platform_fee'),
            earnings=Sum('vendor_earning'),
        )
        .order_by('-gross')
    )
    return render(request, 'quizzes/dashboard/vendor_sales.html', {
        'sales': sales[:100],
        'total_gross': totals['gross'] or 0,
        'total_fees': totals['fees'] or 0,
        'total_payouts': totals['payouts'] or 0,
        'per_vendor': per_vendor,
        'active_page': 'vendor_sales',
    })
