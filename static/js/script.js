// Dashboard and Todo List JavaScript Functions
let subjectToDelete = '';
let todoItems = [];
let todoIdCounter = 1;
 let subjectIndexToDelete = '';

// ========== DASHBOARD FUNCTIONS ==========

// Subject Management Functions
function showUpdateForm(index) {
    document.querySelectorAll('.update-form').forEach(form => form.style.display = 'none');
    document.getElementById('update-form-' + index).style.display = 'block';
}

function hideUpdateForm(index) {
    document.getElementById('update-form-' + index).style.display = 'none';
}

function updateSubject(index, subject) {
    const newMarks = document.getElementById('marks-input-' + index).value;
    const newPriority = document.getElementById('priority-input-' + index).value;
    const newCategory = document.getElementById('category-input-' + index).value;

    const formData = new FormData();
    formData.append('subject', subject.toLowerCase());
    formData.append('marks', newMarks);
    formData.append('priority', newPriority);
    formData.append('category', newCategory);

    fetch("/update", { method: 'POST', body: formData })
    .then(response => {
        if (response.ok) {
            document.getElementById('marks-display-' + index).textContent = newMarks;
            document.getElementById('priority' + index).textContent = newPriority;
            document.getElementById('category' + index).textContent = newCategory;
            hideUpdateForm(index);
        } else {
            alert('Failed to update subject.');
        }
    })
    .catch(err => console.error("Update failed:", err));
}



    function confirmDelete(subject, index) {
        subjectToDelete = subject;
        subjectIndexToDelete = index;
        document.getElementById('deleteSubjectName').textContent = subject;
        document.getElementById('deleteModal').style.display = 'block';
    }

    function closeDeleteModal() {
        document.getElementById('deleteModal').style.display = 'none';
    }

    function deleteSubject() {
        const formData = new FormData();
        formData.append('subject', subjectToDelete.toLowerCase());

        fetch("/delete", { method: 'POST', body: formData })
        .then(response => {
            if (response.ok) {
                document.getElementById('subject-' + subjectIndexToDelete).remove();
            } else {
                alert('Failed to delete subject.');
            }
        });
        closeDeleteModal();
    }

    // Close modal if user clicks outside of it
    window.onclick = function(event) {
        if (event.target == document.getElementById('deleteModal')) {
            closeDeleteModal();
        }
    }

// ========== TODO LIST FUNCTIONS ==========


// Todo Sidebar Functions
let todoOpen = false; // variable to track sidebar state

// Ensure functions are available globally
window.openTodoSidebar = openTodoSidebar;
window.closeTodoSidebar = closeTodoSidebar;
window.addTodoItem = addTodoItem;
window.handleTodoKeyPress = handleTodoKeyPress;

// Test if script is loaded
console.log("Todo functions script loaded successfully");

function openTodoSidebar() {
    const sidebar = document.getElementById('todoSidebar');
    const overlay = document.getElementById('todoOverlay');
    const input = document.getElementById('todoInput');

    if (!todoOpen) {
        // open sidebar
        sidebar.classList.add('open');
        overlay.classList.add('active');
        if (input) input.focus();
        loadTodoItems();   // load items from server
        todoOpen = true;
    } else {
        // close sidebar
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
        todoOpen = false;
    }
}

function closeTodoSidebar(){
    const sidebar = document.getElementById('todoSidebar');
    const overlay = document.getElementById('todoOverlay');
     sidebar.classList.remove('open');
     overlay.classList.remove('active');
     todoOpen = false;
}


function loadTodoItems() {
    console.log("loadTodoItems called");

    fetch("/todo")
        .then(response => {
            console.log("Load todos response status:", response.status);
            return response.json();
        })
        .then(data => {
            console.log("Load todos response data:", data);
            const todoList = document.getElementById("todoList");
            todoList.innerHTML = "";

            if (data.todos && data.todos.length > 0) {
                // Group todos by goal_period
                const grouped = data.todos.reduce((acc, todo) => {
                    const period = todo.goal_period || 'no-period';
                    if (!acc[period]) acc[period] = [];
                    acc[period].push(todo);
                    return acc;
                }, {});

                console.log("Grouped todos:", grouped);

                // Display groups in order: daily, weekly, monthly, no-period
                const order = ['daily', 'weekly', 'monthly', 'no-period'];
                order.forEach((period, index) => {
                    if (grouped[period] && grouped[period].length > 0) {
                        // Add separator line if not first group
                        if (index > 0 && todoList.children.length > 0) {
                            const separator = document.createElement("div");
                            separator.style.cssText = "height: 1px; background-color: #e0e0e0; margin: 15px 0 10px 0;";
                            todoList.appendChild(separator);
                        }

                        // Group header with better styling
                        const groupHeader = document.createElement("div");
                        groupHeader.className = "todo-group-header";
                        groupHeader.style.cssText = `
                            color: #999;
                            font-size: 0.75em;
                            font-style: italic;
                            font-weight: 500;
                            text-transform: uppercase;
                            letter-spacing: 0.5px;
                            margin-bottom: 8px;
                            padding-left: 4px;
                        `;

                        if (period === 'no-period') {
                            groupHeader.textContent = 'Other Tasks';
                        } else {
                            groupHeader.textContent = period.charAt(0).toUpperCase() + period.slice(1) + ' Goals';
                        }
                        todoList.appendChild(groupHeader);

                        grouped[period].forEach(todo => {
                            const todoDiv = document.createElement("div");
                            todoDiv.className = "todo-item";
                            todoDiv.setAttribute("data-id", todo._id);
                            todoDiv.style.cssText = "display: flex; align-items: center; padding: 8px 4px; margin-bottom: 4px;";

                            // checkbox
                            const checkbox = document.createElement("input");
                            checkbox.type = "checkbox";
                            checkbox.className = "todo-checkbox";
                            checkbox.checked = Boolean(todo.completion_status);
                            checkbox.style.cssText = "margin-right: 10px; cursor: pointer;";
                            checkbox.addEventListener('change', function(e) {
                                e.preventDefault();
                                console.log("Checkbox changed for todo ID:", todo._id);
                                markTodoDone(todo._id);
                            });

                            // text span
                            const textSpan = document.createElement("span");
                            textSpan.className = "todo-text";
                            textSpan.textContent = todo.task;
                            textSpan.style.cssText = "flex: 1; cursor: pointer;";

                            // Apply strikethrough and opacity based on completion status
                            if (todo.completion_status) {
                                textSpan.style.textDecoration = "line-through";
                                textSpan.style.opacity = "0.6";
                                textSpan.style.color = "#888";
                                todoDiv.style.opacity = "0.7";
                            } else {
                                textSpan.style.textDecoration = "none";
                                textSpan.style.opacity = "1";
                                textSpan.style.color = "inherit";
                                todoDiv.style.opacity = "1";
                            }

                            todoDiv.appendChild(checkbox);
                            todoDiv.appendChild(textSpan);
                            todoList.appendChild(todoDiv);
                        });
                    }
                });
            } else {
                const emptyDiv = document.createElement("div");
                emptyDiv.className = "todo-empty";
                emptyDiv.textContent = "No tasks yet. Add one above!";
                todoList.appendChild(emptyDiv);
            }
        })
        .catch(err => {
            console.error("Error loading todos:", err);
            const todoList = document.getElementById("todoList");
            todoList.innerHTML = '<div class="todo-empty">Error loading todos. Check console.</div>';
        });
}


function addTodoItem() {
    console.log("addTodoItem called");

    const taskInput = document.getElementById("todoInput");
    const goalPeriodSelect = document.getElementById("todoGoalPeriod");

    if (!taskInput) {
        console.error("todoInput element not found");
        alert("Error: Task input not found");
        return;
    }

    if (!goalPeriodSelect) {
        console.error("todoGoalPeriod element not found");
        alert("Error: Goal period dropdown not found");
        return;
    }

    const task = taskInput.value;
    const goal_period = goalPeriodSelect.value;

    console.log("Task:", task, "Goal period:", goal_period);

    if (!task || !task.trim()) {
        alert("Task cannot be empty");
        return;
    }

    if (!goal_period) {
        alert("Please select a goal period");
        return;
    }

    console.log("Sending request to /todo/add");

    fetch("/todo/add", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            task: task.trim(),
            goal_period: goal_period
        })
    })
    .then(res => {
        console.log("Response status:", res.status);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        console.log("Response data:", data);
        if (data.success) {
            taskInput.value = "";
            goalPeriodSelect.value = "";
            console.log("Task added successfully, reloading list");
            loadTodoItems();
        } else {
            alert("Failed to add task: " + (data.error || "Unknown error"));
        }
    })
    .catch(error => {
        console.error("Fetch error:", error);
        alert("Error adding task: " + error.message);
    });
}

// Function to check for deadline warnings
function checkDeadlineWarnings() {
    fetch("/todo/check-deadlines", {
        method: "GET",
        headers: {"Content-Type": "application/json"}
    })
    .then(res => res.json())
    .then(data => {
        if (data.expiredTasks && data.expiredTasks.length > 0) {
            const taskNames = data.expiredTasks.map(task => `• ${task.task}`).join('\n');
            const confirmed = confirm(`⚠️ WARNING: These tasks have reached their deadline and will be deleted:\n\n${taskNames}\n\nPress OK to acknowledge and delete these tasks.`);

            if (confirmed) {
                // Refresh the todo list to show updated data
                loadTodoItems();
            }
        }
    })
    .catch(error => {
        console.error("Error checking deadlines:", error);
    });
}

function openTodoSidebar() {
    const sidebar = document.getElementById('todoSidebar');
    const overlay = document.getElementById('todoOverlay');
    const input = document.getElementById('todoInput');

    if (!todoOpen) {
        sidebar.classList.add('open');
        overlay.classList.add('active');
        if (input) input.focus();
        loadTodoItems();
        checkDeadlineWarnings(); // Check for expired tasks
        todoOpen = true;
    } else {
        sidebar.classList.remove('open');
        overlay.classList.remove('active');
        todoOpen = false;
    }
}

// delete todo
function markTodoDone(id) {
    console.log("markTodoDone called with ID:", id); // Debug log

    // Find the checkbox to prevent visual flicker
    const todoItem = document.querySelector(`[data-id="${id}"]`);
    const checkbox = todoItem ? todoItem.querySelector('.todo-checkbox') : null;

    fetch("/todo/done", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id })
    })
    .then(res => {
        console.log("Mark done response status:", res.status); // Debug log
        return res.json();
    })
    .then(data => {
        console.log("Mark done response data:", data); // Debug log
        if (data.success) {
            // Immediately reload to get the updated state from server
            loadTodoItems();
        } else {
            console.error("Failed to mark todo done:", data.error);
            // Revert checkbox if there was an error
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
            }
        }
    })
    .catch(err => {
        console.error("Error marking todo done:", err);
        // Revert checkbox if there was an error
        if (checkbox) {
            checkbox.checked = !checkbox.checked;
        }
    });
}
async function loadCharts() {
    try {
        // Fetch stats from the backend
        const response = await fetch('/todo_stats');
        const stats = await response.json();

        if (!response.ok) {
            console.error('Failed to fetch stats:', stats.error);
            return;
        }

        const ctx = document.getElementById('goalChart').getContext('2d');

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                datasets: [
                    {
                        label: 'Daily Goals',
                        data: [stats.daily.completed, Math.max(0, stats.daily.total - stats.daily.completed)],
                        backgroundColor: ['#6A994E', '#D9D9D9'],
                        borderColor: ['#5A8A3E', '#C9C9C9'],
                        borderWidth: 2,
                        circumference: 360,
                        cutout: '70%'   // innermost ring
                    },
                    {
                        label: 'Weekly Goals',
                        data: [stats.weekly.completed, Math.max(0, stats.weekly.total - stats.weekly.completed)],
                        backgroundColor: ['#F2B705', '#ECECEC'],
                        borderColor: ['#E2A705', '#DCDCDC'],
                        borderWidth: 2,
                        circumference: 360,
                        cutout: '55%'   // middle ring
                    },
                    {
                        label: 'Monthly Goals',
                        data: [stats.monthly.completed, Math.max(0, stats.monthly.total - stats.monthly.completed)],
                        backgroundColor: ['#3A86FF', '#E5E5E5'],
                        borderColor: ['#2A76EF', '#D5D5D5'],
                        borderWidth: 2,
                        circumference: 360,
                        cutout: '40%'   // outermost ring
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            color: '#F5F3F0',
                            font: {
                                size: 12,
                                weight: '600'
                            },
                            padding: 15
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const dataset = context.dataset;
                                const total = dataset.data[0] + dataset.data[1];
                                const current = context.parsed;
                                const percentage = total > 0 ? Math.round((current / total) * 100) : 0;

                                if (context.dataIndex === 0) {
                                    return `${dataset.label}: ${current}/${total} (${percentage}%)`;
                                }
                                return null; // Don't show tooltip for incomplete portion
                            }
                        },
                        backgroundColor: 'rgba(62, 63, 41, 0.9)',
                        titleColor: '#F5F3F0',
                        bodyColor: '#BCA88D',
                        borderColor: '#BCA88D',
                        borderWidth: 1
                    }
                },
                animation: {
                    animateRotate: true,
                    animateScale: true,
                    duration: 1000
                }
            }
        });

        // Display stats summary
        displayStatsSummary(stats);

    } catch (error) {
        console.error('Error loading charts:', error);
    }
}

function displayStatsSummary(stats) {
    const summaryContainer = document.getElementById('stats-summary');
    if (!summaryContainer) return;

    const totalGoals = stats.daily.total + stats.weekly.total + stats.monthly.total;
    const totalCompleted = stats.daily.completed + stats.weekly.completed + stats.monthly.completed;
    const overallPercentage = totalGoals > 0 ? Math.round((totalCompleted / totalGoals) * 100) : 0;

    summaryContainer.innerHTML = `
        <div class="stats-grid">
            <div class="stat-item">
                <span class="stat-number">${stats.daily.completed}/${stats.daily.total}</span>
                <span class="stat-label">Daily</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${stats.weekly.completed}/${stats.weekly.total}</span>
                <span class="stat-label">Weekly</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${stats.monthly.completed}/${stats.monthly.total}</span>
                <span class="stat-label">Monthly</span>
            </div>
            <div class="stat-item overall">
                <span class="stat-number">${overallPercentage}%</span>
                <span class="stat-label">Overall</span>
            </div>
        </div>
    `;
}

// Load charts when DOM is ready
document.addEventListener("DOMContentLoaded", loadCharts);

// Reload charts when todo sidebar closes to update stats
function closeTodoSidebar(){
    const sidebar = document.getElementById('todoSidebar');
    const overlay = document.getElementById('todoOverlay');
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
    todoOpen = false;

    // Reload charts to update progress
    loadCharts();
}
// allow Enter key to add
function handleTodoKeyPress(event) {
    if (event.key === "Enter") {
        addTodoItem();
    }
}

// Test function - you can call this in console to test if functions work
window.testTodoFunctions = function() {
    console.log("Testing todo functions...");

    // Test if elements exist
    const elements = {
        todoInput: document.getElementById("todoInput"),
        todoGoalPeriod: document.getElementById("todoGoalPeriod"),
        todoAddBtn: document.getElementById("todoAddBtn"),
        todoList: document.getElementById("todoList")
    };

    console.log("Elements found:", elements);

    // Test if functions exist
    const functions = {
        addTodoItem: typeof window.addTodoItem,
        loadTodoItems: typeof loadTodoItems,
        markTodoDone: typeof markTodoDone
    };

    console.log("Function types:", functions);

    return { elements, functions };
};
// Test function - you can call this in console to test if functions work
window.testTodoFunctions = function() {
    console.log("Testing todo functions...");

    // Test if elements exist
    const elements = {
        todoInput: document.getElementById("todoInput"),
        todoGoalPeriod: document.getElementById("todoGoalPeriod"),
        todoAddBtn: document.getElementById("todoAddBtn"),
        todoList: document.getElementById("todoList")
    };

    console.log("Elements found:", elements);

    // Test if functions exist
    const functions = {
        addTodoItem: typeof window.addTodoItem,
        loadTodoItems: typeof loadTodoItems,
        markTodoDone: typeof markTodoDone
    };

    console.log("Function types:", functions);

    return { elements, functions };
};


// ========== UTILITY FUNCTIONS ==========

// Escape HTML to prevent XSS
function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// Format time for display
function formatTime(minutes) {
    if (minutes >= 60) {
        const hours = Math.floor(minutes / 60);
        const remainingMinutes = minutes % 60;
        return hours + 'h ' + remainingMinutes + 'm';
    }
    return minutes + 'm';
}

// ========== EVENT LISTENERS ==========

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('deleteModal');
    if (event.target === modal) {
        closeDeleteModal();
    }
}
//Calender
let calendar;
let calendarInitialized = false;

// Calendar Functions
function toggleCalendar() {
    const popup = document.getElementById("calendar");
    const overlay = document.getElementById("calendarOverlay");

    if (popup.classList.contains("calendar-open")) {
        closeCalendar();
    } else {
        popup.classList.add("calendar-open");
        if (overlay) overlay.classList.add("calendar-active");

        if (!calendarInitialized) {
            initializeCalendar();
        }
    }
}

function closeCalendar() {
    const popup = document.getElementById("calendar");
    const overlay = document.getElementById("calendarOverlay");

    popup.classList.remove("calendar-open");
    if (overlay) overlay.classList.remove("calendar-active");
}

// Initialize Simple Calendar
function initializeCalendar() {
    const calendarEl = document.getElementById("calendarContent");

    calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        height: 'auto',
        selectable: true,
        headerToolbar: {
            left: 'prev,next',
            center: 'title',
            right: 'today'
        },
        events: "/reminders",
        dateClick: function(info) {
            // Only allow adding reminders for today or future dates
            const today = new Date();
            const selectedDate = new Date(info.dateStr);

            if (selectedDate >= today.setHours(0,0,0,0)) {
                const title = prompt("Enter reminder:");
                if (title && title.trim()) {
                    addReminder(title.trim(), info.dateStr);
                }
            } else {
                alert("Cannot add reminders for past dates!");
            }
        }
    });

    calendar.render();
    calendarInitialized = true;
}

// Add new reminder
function addReminder(title, date) {
    fetch("/reminders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title, date: date })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            calendar.refetchEvents();
            alert("Reminder added successfully!");
        } else {
            alert("Failed to add reminder");
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert("Network error occurred");
    });
}

// Close calendar when clicking overlay
window.addEventListener('click', function(event) {
    const calendarOverlay = document.getElementById('calendarOverlay');
    if (event.target === calendarOverlay) {
        closeCalendar();
    }
});
// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard loaded successfully');
    loadTodoItems();
});