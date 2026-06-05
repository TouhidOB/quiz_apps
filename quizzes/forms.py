from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Department, Quiz, Question, Choice, Package


class GoogleDocUploadForm(forms.Form):
    """Form for uploading questions from a Google Docs link."""
    doc_url = forms.URLField(
        label='Google Docs Link',
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://docs.google.com/document/d/...',
            'id': 'id_doc_url',
        }),
        help_text='Paste a publicly shared Google Docs link. The document must be set to "Anyone with the link can view".'
    )
    clear_existing = forms.BooleanField(
        required=False,
        initial=False,
        label='Clear existing questions',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'id_clear_existing',
        }),
        help_text='Check this to remove all existing questions before importing new ones.'
    )


class UserRegisterForm(UserCreationForm):
    """Extended user registration form."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email address',
        })
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name',
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name',
        })
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username',
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password',
        })


# ─── Custom Dashboard Forms ────────────────────────────────────


BOOTSTRAP_ICON_CHOICES = [
    ('bi-mortarboard-fill', '🎓 Mortarboard'),
    ('bi-code-slash', '💻 Code'),
    ('bi-building', '🏗️ Building'),
    ('bi-layers-fill', '📚 Layers'),
    ('bi-lightning-charge', '⚡ Lightning'),
    ('bi-graph-up-arrow', '📈 Graph'),
    ('bi-shield-lock-fill', '🔒 Shield'),
    ('bi-gear-fill', '⚙️ Gear'),
    ('bi-cpu-fill', '🖥️ CPU'),
    ('bi-heart-pulse-fill', '❤️ Heart Pulse'),
    ('bi-truck', '🚚 Truck'),
    ('bi-wrench-adjustable', '🔧 Wrench'),
    ('bi-calculator-fill', '🧮 Calculator'),
    ('bi-briefcase-fill', '💼 Briefcase'),
    ('bi-bank2', '🏦 Bank'),
    ('bi-palette-fill', '🎨 Palette'),
    ('bi-camera-fill', '📷 Camera'),
    ('bi-music-note-beamed', '🎵 Music'),
    ('bi-translate', '🌐 Translate'),
    ('bi-droplet-fill', '💧 Droplet'),
]


class DepartmentForm(forms.ModelForm):
    """Form for creating/editing departments from the custom dashboard."""
    icon = forms.ChoiceField(
        choices=BOOTSTRAP_ICON_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_icon',
        })
    )

    class Meta:
        model = Department
        fields = ('name', 'description', 'icon', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Civil Engineering',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Brief description of this department...',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class QuizForm(forms.ModelForm):
    """Form for creating/editing quizzes from the custom dashboard."""
    class Meta:
        model = Quiz
        fields = (
            'department', 'name', 'prerequisites',
            'total_questions', 'mark_per_question', 'pass_mark',
            'time_limit', 'is_published', 'allow_retake', 'shuffle_questions',
            'show_instant_feedback', 'per_question_time_limit'
        )
        widgets = {
            'department': forms.Select(attrs={
                'class': 'form-select',
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Python Fundamentals',
            }),
            'prerequisites': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'List prerequisites or knowledge required...',
            }),
            'total_questions': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
            }),
            'mark_per_question': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.25',
                'min': '0.25',
            }),
            'pass_mark': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '0',
            }),
            'time_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'placeholder': 'Minutes',
            }),
            'per_question_time_limit': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 5,
                'placeholder': 'Seconds (optional)',
            }),
            'is_published': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'allow_retake': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'shuffle_questions': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'show_instant_feedback': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class ManualQuestionForm(forms.Form):
    """Form for manually adding a single question with choices."""
    question_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Enter the question text...',
        }),
        label='Question'
    )
    choice_a = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option A',
        }),
        label='Option A'
    )
    choice_b = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option B',
        }),
        label='Option B'
    )
    choice_c = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option C (optional)',
        }),
        label='Option C'
    )
    choice_d = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Option D (optional)',
        }),
        label='Option D'
    )
    correct_answer = forms.ChoiceField(
        choices=[
            ('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D'),
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'form-check-input',
        }),
        label='Correct Answer'
    )


class QuestionEditForm(forms.Form):
    """Form for editing an existing question + its choices."""
    question_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
        }),
        label='Question'
    )
    explanation = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Explain why the correct answer is right (optional)...',
        }),
        label='Explanation'
    )
    choice_a = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Option A'
    )
    choice_b = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Option B'
    )
    choice_c = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Option C'
    )
    choice_d = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='Option D'
    )
    correct_answer = forms.ChoiceField(
        choices=[
            ('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label='Correct Answer'
    )


class EmployeeForm(forms.ModelForm):
    """Form for adding staff/employee users for special tasks."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Set a password',
        }),
        min_length=6,
    )
    ROLE_CHOICES = [
        ('staff', 'Staff — Can upload questions & manage quizzes'),
        ('superuser', 'Admin — Full access to everything'),
    ]
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
        }),
        label='Role',
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Username',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'First name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Last name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address',
            }),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        role = self.cleaned_data['role']
        user.is_staff = True
        if role == 'superuser':
            user.is_superuser = True
        if commit:
            user.save()
        return user


class PackageForm(forms.ModelForm):
    """Form for creating/editing quiz packages from the custom dashboard."""
    icon = forms.ChoiceField(
        choices=BOOTSTRAP_ICON_CHOICES + [
            ('bi-box-seam-fill', '📦 Package'),
            ('bi-boxes', '📦 Boxes'),
            ('bi-award-fill', '🏅 Award'),
            ('bi-stars', '⭐ Stars'),
            ('bi-gem', '💎 Gem'),
            ('bi-rocket-takeoff-fill', '🚀 Rocket'),
        ],
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_icon',
        })
    )

    quizzes = forms.ModelMultipleChoiceField(
        queryset=Quiz.objects.filter(is_published=True).order_by('department__name', 'name'),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select d-none',
            'id': 'id_quizzes',
        }),
        required=False,
        help_text='Select the quizzes to include in this package.'
    )

    class Meta:
        model = Package
        fields = ('name', 'description', 'icon', 'price', 'discount_price', 'quizzes', 'is_active')
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g. Complete Civil Engineering Bundle',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the package, what it covers, and who should enroll...',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
            'discount_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Optional sale price',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class CSVJSONUploadForm(forms.Form):
    """Form for uploading CSV or JSON question files."""
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.json',
        }),
        help_text='Upload a .csv or .json file with questions.'
    )
    clear_existing = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='Replace existing questions',
        help_text='If checked, all existing questions will be deleted before import.'
    )
