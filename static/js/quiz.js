/* ═══════════════════════════════════════════════════════════
   QuizMaster – jQuery Quiz Engine
   ═══════════════════════════════════════════════════════════ */

/**
 * Initialize the countdown timer for quiz-taking.
 * @param {number} totalSeconds - Total time in seconds.
 */
function initQuizTimer(totalSeconds) {
    let remaining = totalSeconds;
    const $display = $('#timerDisplay');
    const $progressBar = $('#timerProgressBar');
    const $timerBar = $('#timerBar');

    function updateTimer() {
        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        const timeStr = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        $display.text(timeStr);

        // Progress bar
        const percent = (remaining / totalSeconds) * 100;
        $progressBar.css('width', percent + '%');

        // Color states
        if (remaining <= 60) {
            $display.removeClass('warning').addClass('danger');
            $progressBar.removeClass('warning').addClass('danger');
        } else if (remaining <= totalSeconds * 0.25) {
            $display.removeClass('danger').addClass('warning');
            $progressBar.removeClass('danger').addClass('warning');
        }

        if (remaining <= 0) {
            clearInterval(timerInterval);
            autoSubmitQuiz();
            return;
        }

        remaining--;
    }

    const timerInterval = setInterval(updateTimer, 1000);
    updateTimer(); // Initial call
}

/**
 * Auto-submit the quiz when time runs out.
 */
function autoSubmitQuiz() {
    // Show modal
    const modal = new bootstrap.Modal($('#timeUpModal')[0]);
    modal.show();

    // Submit after short delay for UX
    setTimeout(function() {
        $('#quizForm').submit();
    }, 1500);
}

/**
 * Initialize choice selection handlers.
 * @param {number} totalQuestions - Total number of questions.
 */
function initChoiceHandlers(totalQuestions) {
    window._answeredSet = window._answeredSet || new Set();

    // Choice click handler
    $(document).on('click', '.choice-option', function() {
        const $this = $(this);
        const $input = $this.find('input[type="radio"]');
        const $card = $this.closest('.question-card');
        const questionNum = $card.data('question');

        // Deselect siblings
        $this.siblings('.choice-option').removeClass('selected');
        $this.addClass('selected');
        $input.prop('checked', true);

        // Mark question card
        $card.addClass('answered');

        // Update progress dot
        $(`#dot-${questionNum}`).addClass('answered');

        // Track answered
        window._answeredSet.add(questionNum);
        updateAnswerCount(window._answeredSet.size, totalQuestions);
        updateQuestionProgress(window._answeredSet.size, totalQuestions);
    });

    // Submit confirmation
    $('#quizForm').on('submit', function(e) {
        const unanswered = totalQuestions - window._answeredSet.size;
        if (unanswered > 0) {
            const confirmed = confirm(
                `You have ${unanswered} unanswered question(s). Are you sure you want to submit?`
            );
            if (!confirmed) {
                e.preventDefault();
                return false;
            }
        }

        // Disable button to prevent double submit
        $('#submitBtn').prop('disabled', true).html(
            '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...'
        );
    });

    // Smooth scroll for progress dots (now navigates in paginated mode)
    $(document).on('click', '.progress-dot', function(e) {
        e.preventDefault();
        const questionNum = $(this).data('question');
        if (window._goToQuestion) {
            window._goToQuestion(questionNum);
        }
    });
}

/**
 * Update the answered/remaining counters.
 */
function updateAnswerCount(answered, total) {
    $('#answeredCount').text(answered);
    $('#sidebarAnswered').text(answered);
    $('#sidebarRemaining').text(total - answered);
}

/**
 * Update the question progress bar.
 */
function updateQuestionProgress(answered, total) {
    const percent = Math.round((answered / total) * 100);
    $('#questionProgressFill').css('width', percent + '%');
    $('#progressPercent').text(percent + '%');
}

/**
 * Initialize Previous / Next question navigation (paginated mode).
 * @param {number} totalQuestions - Total number of questions.
 */
function initQuizNavigation(totalQuestions) {
    let currentQuestion = 1;

    const $prevBtn = $('#prevBtn');
    const $nextBtn = $('#nextBtn');
    const $navIndicator = $('#navIndicator');
    const $submitSection = $('#submitSection');

    function showQuestion(num) {
        // Hide all questions
        $('.question-card').addClass('q-hidden');
        // Show target
        $(`#question-${num}`).removeClass('q-hidden');

        // Update current dot
        $('.progress-dot').removeClass('current');
        $(`#dot-${num}`).addClass('current');

        // Update indicator
        $navIndicator.text(`${num} / ${totalQuestions}`);
        $('#progressText').text(`Question ${num} of ${totalQuestions}`);

        // Button states
        $prevBtn.prop('disabled', num <= 1);

        if (num >= totalQuestions) {
            $nextBtn.html('Submit <i class="bi bi-check-circle-fill ms-1"></i>')
                     .removeClass('btn-gradient').addClass('btn-gradient');
            $submitSection.css('display', '').show();
        } else {
            $nextBtn.html('Next <i class="bi bi-chevron-right ms-1"></i>');
            $submitSection.hide();
        }

        currentQuestion = num;

        // Scroll to top of quiz
        $('html, body').animate({
            scrollTop: $('#timerBar').offset().top - 100
        }, 200);
    }

    // Expose for progress dot clicks
    window._goToQuestion = function(num) {
        if (num >= 1 && num <= totalQuestions) {
            showQuestion(num);
        }
    };

    $prevBtn.on('click', function() {
        if (currentQuestion > 1) {
            showQuestion(currentQuestion - 1);
        }
    });

    $nextBtn.on('click', function() {
        if (currentQuestion < totalQuestions) {
            showQuestion(currentQuestion + 1);
        } else {
            // On last question, clicking "Submit" triggers form submit
            $('#submitBtn').click();
        }
    });

    // Initial state
    showQuestion(1);
}

/**
 * Anti-cheat: disable right-click and text selection during quiz.
 */
function initAntiCheat() {
    // Disable right-click inside the quiz
    $(document).on('contextmenu', '.quiz-secure-zone', function(e) {
        e.preventDefault();
        return false;
    });

    // Disable keyboard shortcuts for copy/paste/view-source
    $(document).on('keydown', function(e) {
        // Ctrl+C, Ctrl+U, Ctrl+Shift+I, F12
        if (
            (e.ctrlKey && (e.key === 'c' || e.key === 'C' || e.key === 'u' || e.key === 'U')) ||
            (e.ctrlKey && e.shiftKey && (e.key === 'I' || e.key === 'i')) ||
            e.key === 'F12'
        ) {
            if ($('.quiz-secure-zone').length) {
                e.preventDefault();
                return false;
            }
        }
    });

    // Disable drag
    $(document).on('dragstart', '.quiz-secure-zone', function(e) {
        e.preventDefault();
        return false;
    });
}

/**
 * Auto-dismiss alerts after 5 seconds.
 */
$(document).ready(function() {
    // Auto-dismiss alerts
    setTimeout(function() {
        $('.alert-dismissible').each(function() {
            const alert = bootstrap.Alert.getOrCreateInstance(this);
            $(this).fadeOut(300, function() {
                alert.close();
            });
        });
    }, 5000);

    // Add fade-in animation to cards on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                $(entry.target).addClass('fade-in-up');
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Observe cards for scroll animation
    $('.glass-card, .question-card, .review-card').each(function() {
        observer.observe(this);
    });
});
