from django.urls import path
from . import views

urlpatterns = [
    # Public
    path('', views.home, name='home'),
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('faq/', views.faq_view, name='faq'),
    path('departments/', views.departments_view, name='departments'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),

    # Packages
    path('packages/', views.packages_list, name='packages'),
    path('package/<slug:slug>/', views.package_detail, name='package_detail'),
    path('package/<slug:slug>/purchase/', views.package_purchase, name='package_purchase'),

    # SSLCommerz Payment Callbacks
    path('payment/success/', views.payment_success, name='payment_success'),
    path('payment/fail/', views.payment_fail, name='payment_fail'),
    path('payment/cancel/', views.payment_cancel, name='payment_cancel'),
    path('payment/ipn/', views.payment_ipn, name='payment_ipn'),

    # Auth
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),

    # Department & Quiz
    path('department/<slug:slug>/', views.department_quizzes, name='department_quizzes'),
    path('quiz/<slug:slug>/', views.quiz_detail, name='quiz_detail'),
    path('quiz/<slug:slug>/take/', views.take_quiz, name='take_quiz'),
    path('quiz/<slug:slug>/submit/', views.submit_quiz, name='submit_quiz'),
    path('quiz/<slug:slug>/upload/', views.upload_questions, name='upload_questions'),

    # Results
    path('result/<uuid:attempt_id>/', views.quiz_result, name='quiz_result'),

    # ─── Custom Admin Dashboard ──────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),

    # Dashboard: Departments
    path('dashboard/departments/', views.dashboard_departments, name='dashboard_departments'),
    path('dashboard/departments/create/', views.dashboard_department_create, name='dashboard_department_create'),
    path('dashboard/departments/<int:pk>/edit/', views.dashboard_department_edit, name='dashboard_department_edit'),
    path('dashboard/departments/<int:pk>/delete/', views.dashboard_department_delete, name='dashboard_department_delete'),

    # Dashboard: Quizzes
    path('dashboard/quizzes/', views.dashboard_quizzes, name='dashboard_quizzes'),
    path('dashboard/quizzes/create/', views.dashboard_quiz_create, name='dashboard_quiz_create'),
    path('dashboard/quizzes/<int:pk>/edit/', views.dashboard_quiz_edit, name='dashboard_quiz_edit'),
    path('dashboard/quizzes/<int:pk>/delete/', views.dashboard_quiz_delete, name='dashboard_quiz_delete'),

    # Dashboard: Questions
    path('dashboard/quizzes/<int:pk>/questions/', views.dashboard_quiz_questions, name='dashboard_quiz_questions'),
    path('dashboard/quizzes/<int:pk>/questions/add-manual/', views.dashboard_add_question_manual, name='dashboard_add_question_manual'),
    path('dashboard/quizzes/<int:pk>/questions/add-gdoc/', views.dashboard_add_question_gdoc, name='dashboard_add_question_gdoc'),
    path('dashboard/questions/<int:pk>/delete/', views.dashboard_delete_question, name='dashboard_delete_question'),

    # Dashboard: All Questions (paginated management)
    path('dashboard/questions/', views.dashboard_all_questions, name='dashboard_all_questions'),
    path('dashboard/questions/<int:pk>/edit/', views.dashboard_edit_question, name='dashboard_edit_question'),

    # Dashboard: Employees
    path('dashboard/employees/', views.dashboard_employees, name='dashboard_employees'),
    path('dashboard/employees/create/', views.dashboard_employee_create, name='dashboard_employee_create'),
    path('dashboard/employees/<int:pk>/toggle/', views.dashboard_employee_toggle, name='dashboard_employee_toggle'),

    # Dashboard: Attempts
    path('dashboard/attempts/', views.dashboard_attempts, name='dashboard_attempts'),

    # Dashboard: Packages
    path('dashboard/packages/', views.dashboard_packages, name='dashboard_packages'),
    path('dashboard/packages/create/', views.dashboard_package_create, name='dashboard_package_create'),
    path('dashboard/packages/<int:pk>/edit/', views.dashboard_package_edit, name='dashboard_package_edit'),
    path('dashboard/packages/<int:pk>/delete/', views.dashboard_package_delete, name='dashboard_package_delete'),

    # ─── New Features ────────────────────────────────────────

    # Bookmarks
    path('bookmarks/', views.bookmarks_list, name='bookmarks'),
    path('bookmark/toggle/', views.toggle_bookmark, name='toggle_bookmark'),

    # Certificate
    path('certificate/<uuid:attempt_id>/', views.download_certificate, name='download_certificate'),

    # CSV/JSON Import (Dashboard)
    path('dashboard/quizzes/<int:pk>/questions/import-file/', views.dashboard_import_csv_json, name='dashboard_import_csv_json'),
]
