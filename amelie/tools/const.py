class TaskPriority:
    """
    Priorities that can be given to Celery background tasks.
    10 is the highest priority, 1 is the lowest. 5 is the default priority for tasks if not specified.
    """

    PRIORITY_10: int = 10
    PRIORITY_9: int = 9
    PRIORITY_8: int = 8
    PRIORITY_7: int = 7
    PRIORITY_6: int = 6
    PRIORITY_5: int = 5
    PRIORITY_4: int = 4
    PRIORITY_3: int = 3
    PRIORITY_2: int = 2
    PRIORITY_1: int = 1

    URGENT: int = PRIORITY_8
    HIGH: int = PRIORITY_6
    DEFAULT: int = PRIORITY_5
    MEDIUM: int = PRIORITY_4
    LOW: int = PRIORITY_2

# Some shorthands that can be imported directly if preferred
TASK_PRIORITY_URGENT = TaskPriority.URGENT
TASK_PRIORITY_HIGH = TaskPriority.HIGH
TASK_PRIORITY_DEFAULT = TaskPriority.DEFAULT
TASK_PRIORITY_MEDIUM = TaskPriority.MEDIUM
TASK_PRIORITY_LOW = TaskPriority.LOW
