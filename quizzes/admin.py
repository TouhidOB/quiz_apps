from django.contrib import admin
from .models import (
    Department, Quiz, Question, Choice,
    QuizAttempt, UserAnswer, GoogleDocUpload,
    Package, PackagePurchase,
    VendorProfile, SubCategory, PlatformSetting,
    QuizPurchase, VendorSale,
)


# ─── Inlines ────────────────────────────────────────────────

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    min_num = 2


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0
    show_change_link = True
    fields = ('text', 'order')


class UserAnswerInline(admin.TabularInline):
    model = UserAnswer
    extra = 0
    readonly_fields = ('question', 'selected_choice')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ─── Model Admins ───────────────────────────────────────────

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'quiz_count', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active',)

    def quiz_count(self, obj):
        return obj.quizzes.count()
    quiz_count.short_description = 'Quizzes'


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'department', 'owner', 'status', 'price', 'total_questions',
        'question_count_display', 'mark_per_question', 'pass_mark', 'time_limit',
        'is_published', 'created_at'
    )
    list_filter = ('department', 'status', 'is_published', 'created_at')
    search_fields = ('name', 'prerequisites')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_published',)
    inlines = [QuestionInline]
    fieldsets = (
        (None, {
            'fields': ('department', 'name', 'slug', 'prerequisites')
        }),
        ('Quiz Configuration', {
            'fields': (
                'total_questions', 'mark_per_question', 'pass_mark',
                'time_limit', 'allow_retake', 'shuffle_questions'
            )
        }),
        ('Status', {
            'fields': ('is_published',)
        }),
    )

    def question_count_display(self, obj):
        count = obj.question_count
        total = obj.total_questions
        if count >= total:
            return f'✅ {count}/{total}'
        return f'⚠️ {count}/{total}'
    question_count_display.short_description = 'Questions Uploaded'


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'quiz', 'order')
    list_filter = ('quiz',)
    search_fields = ('text',)
    inlines = [ChoiceInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'quiz', 'score', 'total_marks',
        'passed', 'started_at', 'completed_at'
    )
    list_filter = ('passed', 'quiz', 'started_at')
    search_fields = ('user__username', 'quiz__name')
    readonly_fields = (
        'user', 'quiz', 'score', 'total_marks',
        'passed', 'started_at', 'completed_at'
    )
    inlines = [UserAnswerInline]

    def has_add_permission(self, request):
        return False


@admin.register(GoogleDocUpload)
class GoogleDocUploadAdmin(admin.ModelAdmin):
    list_display = (
        'quiz', 'status', 'questions_imported',
        'uploaded_by', 'created_at'
    )
    list_filter = ('status', 'created_at')
    readonly_fields = (
        'quiz', 'doc_url', 'uploaded_by', 'status',
        'questions_imported', 'error_message', 'created_at'
    )

    def has_add_permission(self, request):
        return False


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'owner', 'status', 'price', 'discount_price', 'is_active', 'quiz_count', 'enrollment_count', 'created_at')
    list_filter = ('is_active', 'status', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active',)
    filter_horizontal = ('quizzes',)

    def quiz_count(self, obj):
        return obj.quiz_count
    quiz_count.short_description = 'Quizzes'

    def enrollment_count(self, obj):
        return obj.enrollment_count
    enrollment_count.short_description = 'Enrolled'


@admin.register(PackagePurchase)
class PackagePurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'package', 'payment_status', 'amount_paid', 'purchased_at')
    list_filter = ('payment_status', 'purchased_at', 'package')
    search_fields = ('user__username', 'package__name')
    readonly_fields = ('user', 'package', 'purchased_at')

    def has_add_permission(self, request):
        return False


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'user', 'status', 'total_sales', 'total_earnings', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('store_name', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'approved_at', 'approved_by')


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'is_active', 'is_approved', 'created_by', 'created_at')
    list_filter = ('is_active', 'is_approved', 'department')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_active', 'is_approved')


@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'vendor_fee_per_sale', 'updated_at')

    def has_add_permission(self, request):
        return not PlatformSetting.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(QuizPurchase)
class QuizPurchaseAdmin(admin.ModelAdmin):
    list_display = ('user', 'quiz', 'payment_status', 'amount_paid', 'purchased_at')
    list_filter = ('payment_status', 'purchased_at')
    search_fields = ('user__username', 'quiz__name')
    readonly_fields = ('user', 'quiz', 'purchased_at')

    def has_add_permission(self, request):
        return False


@admin.register(VendorSale)
class VendorSaleAdmin(admin.ModelAdmin):
    list_display = ('vendor', 'sale_type', 'buyer', 'sale_amount', 'platform_fee', 'vendor_earning', 'created_at')
    list_filter = ('sale_type', 'created_at')
    search_fields = ('vendor__username', 'buyer__username')
    readonly_fields = (
        'vendor', 'buyer', 'sale_type', 'quiz', 'package',
        'quiz_purchase', 'package_purchase', 'sale_amount',
        'platform_fee', 'vendor_earning', 'created_at'
    )

    def has_add_permission(self, request):
        return False

