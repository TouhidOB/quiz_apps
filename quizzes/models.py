import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse


class VendorProfile(models.Model):
    """A third-party vendor account. Created on vendor registration and gated
    behind admin approval before the vendor dashboard becomes accessible."""
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='vendor_profile'
    )
    store_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    website = models.URLField(max_length=300, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )
    rejection_reason = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_vendors'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.store_name} ({self.user.username}) — {self.status}"

    @property
    def is_approved(self):
        return self.status == 'approved'

    @property
    def total_sales(self):
        return self.user.vendor_sales.count()

    @property
    def total_earnings(self):
        agg = self.user.vendor_sales.aggregate(total=models.Sum('vendor_earning'))
        return agg['total'] or Decimal('0.00')

    @property
    def total_fees(self):
        agg = self.user.vendor_sales.aggregate(total=models.Sum('platform_fee'))
        return agg['total'] or Decimal('0.00')


class PlatformSetting(models.Model):
    """Singleton holding platform-wide configuration (admin-editable)."""
    vendor_fee_per_sale = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Fixed fee the platform keeps on each vendor sale. '
                  'The vendor earns (sale price − this fee).'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform Setting'
        verbose_name_plural = 'Platform Settings'

    def __str__(self):
        return f'Platform Settings (fee/sale: {self.vendor_fee_per_sale})'

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Department(models.Model):
    """Dynamic category for grouping quizzes (e.g., Civil Engineer, Software Engineer)."""
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        default='bi-mortarboard-fill',
        help_text='Bootstrap icon class, e.g. bi-gear-fill'
    )
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(
        default=False,
        help_text='Vendor-created categories require admin approval before going public.'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_departments',
        help_text='The vendor who created this category. Empty for admin-created.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('department_quizzes', kwargs={'slug': self.slug})

    @property
    def quiz_count(self):
        return self.quizzes.filter(is_published=True).count()


class SubCategory(models.Model):
    """A subcategory nested under a Department."""
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='subcategories'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        default='bi-folder-fill',
        help_text='Bootstrap icon class, e.g. bi-folder-fill'
    )
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(
        default=False,
        help_text='Vendor-created subcategories require admin approval before going public.'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_subcategories'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['department__name', 'name']
        verbose_name_plural = 'Subcategories'

    def __str__(self):
        return f"{self.department.name} › {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.department.name}-{self.name}")
            self.slug = base
        super().save(*args, **kwargs)

    @property
    def quiz_count(self):
        return self.quizzes.filter(is_published=True).count()


class Quiz(models.Model):
    """A quiz belonging to a department with all mandatory configuration."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('approved', 'Approved / Published'),
        ('rejected', 'Rejected'),
    ]

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    subcategory = models.ForeignKey(
        SubCategory,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='quizzes'
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='owned_quizzes',
        help_text='The vendor who owns this quiz. Empty for platform/admin-owned quizzes.'
    )
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    prerequisites = models.TextField(
        help_text='List prerequisites or knowledge required before taking this quiz.'
    )
    total_questions = models.PositiveIntegerField(
        help_text='Number of questions in this quiz.'
    )
    mark_per_question = models.DecimalField(
        max_digits=5, decimal_places=2, default=1.00,
        help_text='Marks awarded for each correct answer.'
    )
    pass_mark = models.DecimalField(
        max_digits=6, decimal_places=2,
        help_text='Minimum marks required to pass.'
    )
    time_limit = models.PositiveIntegerField(
        help_text='Time limit in minutes to complete the quiz.'
    )
    is_published = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft',
        help_text='Review workflow status. Admin approval sets this to "approved" and publishes the quiz.'
    )
    rejection_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_quizzes'
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Price to purchase this quiz individually. 0 means free/open.'
    )
    allow_retake = models.BooleanField(
        default=True,
        help_text='Allow users to retake this quiz.'
    )
    shuffle_questions = models.BooleanField(
        default=True,
        help_text='Randomize question order for each attempt.'
    )
    show_instant_feedback = models.BooleanField(
        default=False,
        help_text='Show correct answer immediately after selecting a choice.'
    )
    per_question_time_limit = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Optional per-question time limit in seconds. Leave blank for no limit.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Quizzes'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('quiz_detail', kwargs={'slug': self.slug})

    @property
    def total_marks(self):
        return self.total_questions * self.mark_per_question

    @property
    def is_paid(self):
        return self.price and self.price > 0

    @property
    def is_vendor_owned(self):
        return self.owner_id is not None

    @property
    def question_count(self):
        return self.questions.count()

    @property
    def has_enough_questions(self):
        return self.question_count >= self.total_questions


class Question(models.Model):
    """A single question belonging to a quiz."""
    QUESTION_TYPE_CHOICES = [
        ('mcq', 'Multiple Choice (Single Answer)'),
        ('multi', 'Multiple Choice (Multiple Answers)'),
        ('tf', 'True / False'),
        ('short', 'Short Answer'),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    text = models.TextField(help_text='The question text.')
    question_type = models.CharField(
        max_length=10,
        choices=QUESTION_TYPE_CHOICES,
        default='mcq',
        help_text='Type of question.'
    )
    image = models.ImageField(
        upload_to='question_images/',
        null=True, blank=True,
        help_text='Optional image for image-based questions.'
    )
    explanation = models.TextField(
        blank=True,
        help_text='Explanation shown after quiz submission to explain the correct answer.'
    )
    short_answer_text = models.CharField(
        max_length=500, blank=True,
        help_text='Correct answer for short-answer questions (case-insensitive match).'
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order}: {self.text[:80]}"


class Choice(models.Model):
    """An answer option for a question."""
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices'
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        marker = '✓' if self.is_correct else '✗'
        return f"{marker} {self.text[:60]}"


class QuizAttempt(models.Model):
    """Records a user's attempt at a quiz."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    total_marks = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        status = 'Passed' if self.passed else 'Failed'
        return f"{self.user.username} — {self.quiz.name} — {status} ({self.score}/{self.total_marks})"

    @property
    def percentage(self):
        if self.total_marks > 0:
            return round((self.score / self.total_marks) * 100, 1)
        return 0

    @property
    def correct_count(self):
        return self.answers.filter(
            selected_choice__is_correct=True
        ).count()

    @property
    def incorrect_count(self):
        return self.answers.filter(
            selected_choice__is_correct=False
        ).count()


class UserAnswer(models.Model):
    """Records a specific answer within an attempt."""
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE
    )
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f"{self.attempt.user.username} → Q{self.question.order}"

    @property
    def is_correct(self):
        if self.selected_choice:
            return self.selected_choice.is_correct
        return False


class GoogleDocUpload(models.Model):
    """Tracks Google Doc imports for auditing."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='doc_uploads'
    )
    doc_url = models.URLField(max_length=500)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    questions_imported = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Upload for {self.quiz.name} — {self.status}"


class Package(models.Model):
    """A bundle of quizzes that users can purchase/enroll in."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending', 'Pending Review'),
        ('approved', 'Approved / Published'),
        ('rejected', 'Rejected'),
    ]

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='owned_packages',
        help_text='The vendor who owns this package. Empty for platform/admin-owned packages.'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft',
        help_text='Review workflow status. Admin approval sets this to "approved".'
    )
    rejection_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_packages'
    )
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = models.TextField(
        help_text='Describe what this package covers and who it is for.'
    )
    icon = models.CharField(
        max_length=50,
        default='bi-box-seam-fill',
        help_text='Bootstrap icon class, e.g. bi-box-seam-fill'
    )
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Display price. Set to 0 for free packages.'
    )
    discount_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Optional discounted price. Leave empty for no discount.'
    )
    quizzes = models.ManyToManyField(
        Quiz,
        related_name='packages',
        blank=True,
        help_text='Select the quizzes to include in this package.'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('package_detail', kwargs={'slug': self.slug})

    @property
    def is_vendor_owned(self):
        return self.owner_id is not None

    @property
    def quiz_count(self):
        return self.quizzes.filter(is_published=True).count()

    @property
    def total_questions(self):
        return sum(q.total_questions for q in self.quizzes.filter(is_published=True))

    @property
    def enrollment_count(self):
        return self.purchases.count()

    @property
    def effective_price(self):
        """Return the discount price if available, otherwise the regular price."""
        if self.discount_price is not None:
            return self.discount_price
        return self.price

    @property
    def has_discount(self):
        return self.discount_price is not None and self.discount_price < self.price

    @property
    def discount_percentage(self):
        if self.has_discount and self.price > 0:
            return round(((self.price - self.discount_price) / self.price) * 100)
        return 0


class PackagePurchase(models.Model):
    """Records a user's purchase/enrollment in a package."""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='package_purchases'
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.CASCADE,
        related_name='purchases'
    )

    # Payment fields
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending'
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=100, blank=True)
    sslcommerz_val_id = models.CharField(max_length=200, blank=True)
    sslcommerz_tran_date = models.CharField(max_length=100, blank=True)

    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'package')
        ordering = ['-purchased_at']

    def __str__(self):
        return f"{self.user.username} → {self.package.name} ({self.payment_status})"

    @property
    def is_active_purchase(self):
        """Only 'completed' purchases grant access (or free packages)."""
        return self.payment_status == 'completed'


class BookmarkedQuestion(models.Model):
    """Questions bookmarked by users for later review."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookmarked_questions'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='bookmarks'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ★ Q{self.question.order}: {self.question.text[:50]}"


class QuizPurchase(models.Model):
    """Records a user's purchase of an individual quiz."""
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quiz_purchases'
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='purchases'
    )

    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending'
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=100, blank=True)
    sslcommerz_val_id = models.CharField(max_length=200, blank=True)
    sslcommerz_tran_date = models.CharField(max_length=100, blank=True)

    purchased_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'quiz')
        ordering = ['-purchased_at']

    def __str__(self):
        return f"{self.user.username} → {self.quiz.name} ({self.payment_status})"

    @property
    def is_active_purchase(self):
        return self.payment_status == 'completed'


class VendorSale(models.Model):
    """Earnings ledger: one row per completed sale of a vendor-owned quiz or package."""
    SALE_TYPE_CHOICES = [
        ('quiz', 'Quiz'),
        ('package', 'Package'),
    ]

    vendor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='vendor_sales'
    )
    buyer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='purchases_made'
    )
    sale_type = models.CharField(max_length=10, choices=SALE_TYPE_CHOICES)
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vendor_sales'
    )
    package = models.ForeignKey(
        Package,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vendor_sales'
    )
    quiz_purchase = models.OneToOneField(
        QuizPurchase,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vendor_sale'
    )
    package_purchase = models.OneToOneField(
        PackagePurchase,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vendor_sale'
    )
    sale_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    platform_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text='Snapshot of the platform fee at the time of sale.'
    )
    vendor_earning = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        item = self.quiz.name if self.quiz else (self.package.name if self.package else '—')
        return f"{self.vendor.username} ← {item} (+{self.vendor_earning})"
