from sqlalchemy import String, UniqueConstraint, inspect

from app.models import (
    Task,
    TaskCompletionReview,
    TaskInput,
    TaskIssue,
    TaskNode,
    TaskNodeParticipant,
    TaskParticipant,
    TaskProgressReport,
    TaskStatusLog,
    User,
)


def test_user_columns_and_employee_number_primary_key_contract() -> None:
    table = User.__table__

    assert set(table.columns.keys()) == {
        "employee_no",
        "name",
        "department_id",
        "position",
        "manager_employee_no",
        "org_level",
        "wecom_user_id",
        "role_type",
        "status",
    }
    assert [column.name for column in table.primary_key.columns] == ["employee_no"]
    assert isinstance(table.c.employee_no.type, String)
    assert table.c.employee_no.nullable is False
    assert "id" not in table.columns
    assert "user_id" not in table.columns
    assert "employee_id" not in table.columns


def test_user_optional_fields_have_expected_nullability() -> None:
    table = User.__table__

    assert table.c.name.nullable is False
    assert table.c.department_id.nullable is True
    assert table.c.position.nullable is True
    assert table.c.manager_employee_no.nullable is True
    assert table.c.org_level.nullable is True
    assert table.c.wecom_user_id.nullable is True
    assert table.c.role_type.nullable is False
    assert table.c.status.nullable is False


def test_user_foreign_keys_use_explicit_business_identifiers() -> None:
    table = User.__table__

    department_foreign_key = next(iter(table.c.department_id.foreign_keys))
    manager_foreign_key = next(iter(table.c.manager_employee_no.foreign_keys))

    assert department_foreign_key.target_fullname == "departments.department_id"
    assert department_foreign_key.ondelete == "RESTRICT"
    assert manager_foreign_key.target_fullname == "users.employee_no"
    assert manager_foreign_key.ondelete == "RESTRICT"


def test_wecom_user_id_has_one_simple_unique_constraint() -> None:
    table = User.__table__
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in table.indexes
    }

    assert unique_constraints == {("wecom_user_id",)}
    assert ("wecom_user_id",) not in indexed_columns


def test_user_relationships_are_bidirectional_unambiguous_and_safe() -> None:
    relationships = inspect(User).relationships

    assert set(relationships.keys()) == {
        "department",
        "assigned_completion_reviews",
        "closed_task_issues",
        "direct_reports",
        "manager",
        "owned_task_issues",
        "owned_task_nodes",
        "operated_task_status_logs",
        "assigned_tasks",
        "created_tasks",
        "reporting_tasks",
        "reported_task_issues",
        "rejected_task_issues",
        "resolved_task_issues",
        "review_tasks",
        "submitted_task_inputs",
        "submitted_completion_reviews",
        "submitted_progress_reports",
        "task_node_participations",
        "task_participations",
        "targeted_task_status_logs",
    }
    assert relationships.department.back_populates == "users"
    assert {column.name for column in relationships.department.local_columns} == {
        "department_id"
    }
    assert relationships.manager.back_populates == "direct_reports"
    assert relationships.manager.uselist is False
    assert {column.name for column in relationships.manager.local_columns} == {
        "manager_employee_no"
    }
    assert {column.name for column in relationships.manager.remote_side} == {
        "employee_no"
    }
    assert relationships.direct_reports.back_populates == "manager"
    assert relationships.direct_reports.uselist is True
    assert relationships.submitted_task_inputs.back_populates == "submitted_by"
    assert relationships.submitted_task_inputs.uselist is True
    assert relationships.submitted_task_inputs.mapper.class_ is TaskInput
    task_relationships = {
        "created_tasks": ("creator", "creator_employee_no"),
        "assigned_tasks": ("main_assignee", "main_assignee_employee_no"),
        "reporting_tasks": ("report_to", "report_to_employee_no"),
        "review_tasks": ("reviewer", "reviewer_employee_no"),
    }
    for relationship_name, (back_populates, foreign_key_name) in (
        task_relationships.items()
    ):
        relationship = relationships[relationship_name]
        assert relationship.back_populates == back_populates
        assert relationship.uselist is True
        assert relationship.mapper.class_ is Task
        assert {column.name for column in relationship.remote_side} == {
            foreign_key_name
        }

    assert relationships.task_participations.back_populates == "employee"
    assert relationships.task_participations.uselist is True
    assert relationships.task_participations.mapper.class_ is TaskParticipant
    assert relationships.owned_task_nodes.back_populates == "owner"
    assert relationships.owned_task_nodes.uselist is True
    assert relationships.owned_task_nodes.mapper.class_ is TaskNode
    assert relationships.task_node_participations.back_populates == "employee"
    assert relationships.task_node_participations.uselist is True
    assert relationships.task_node_participations.mapper.class_ is TaskNodeParticipant
    status_log_relationships = {
        "operated_task_status_logs": ("operator", "operator_employee_no"),
        "targeted_task_status_logs": ("target_employee", "target_employee_no"),
    }
    for relationship_name, (back_populates, remote_column) in (
        status_log_relationships.items()
    ):
        relationship = relationships[relationship_name]
        assert relationship.back_populates == back_populates
        assert relationship.uselist is True
        assert relationship.mapper.class_ is TaskStatusLog
        assert {column.name for column in relationship.remote_side} == {
            remote_column
        }

    issue_relationships = {
        "reported_task_issues": ("reported_by", "reported_by_employee_no"),
        "owned_task_issues": ("owner", "owner_employee_no"),
        "resolved_task_issues": ("resolved_by", "resolved_by_employee_no"),
        "rejected_task_issues": ("rejected_by", "rejected_by_employee_no"),
        "closed_task_issues": ("closed_by", "closed_by_employee_no"),
    }
    for relationship_name, (back_populates, remote_column) in (
        issue_relationships.items()
    ):
        relationship = relationships[relationship_name]
        assert relationship.back_populates == back_populates
        assert relationship.uselist is True
        assert relationship.mapper.class_ is TaskIssue
        assert {column.name for column in relationship.remote_side} == {
            remote_column
        }

    progress_reports = relationships.submitted_progress_reports
    assert progress_reports.back_populates == "reporter"
    assert progress_reports.uselist is True
    assert progress_reports.mapper.class_ is TaskProgressReport
    assert {column.name for column in progress_reports.remote_side} == {
        "reporter_employee_no"
    }

    completion_review_relationships = {
        "submitted_completion_reviews": (
            "submitted_by",
            "submitted_by_employee_no",
        ),
        "assigned_completion_reviews": (
            "reviewer",
            "reviewer_employee_no",
        ),
    }
    for relationship_name, (back_populates, remote_column) in (
        completion_review_relationships.items()
    ):
        relationship = relationships[relationship_name]
        assert relationship.back_populates == back_populates
        assert relationship.uselist is True
        assert relationship.mapper.class_ is TaskCompletionReview
        assert {column.name for column in relationship.remote_side} == {
            remote_column
        }

    for relationship_name in (
        "department",
        "assigned_completion_reviews",
        "manager",
        "direct_reports",
        "closed_task_issues",
        "submitted_task_inputs",
        "submitted_completion_reviews",
        "created_tasks",
        "assigned_tasks",
        "reporting_tasks",
        "review_tasks",
        "owned_task_nodes",
        "operated_task_status_logs",
        "owned_task_issues",
        "reported_task_issues",
        "rejected_task_issues",
        "resolved_task_issues",
        "submitted_progress_reports",
        "task_node_participations",
        "task_participations",
        "targeted_task_status_logs",
    ):
        cascade = relationships[relationship_name].cascade
        assert "delete" not in cascade
        assert "delete-orphan" not in cascade


def test_user_indexes_are_non_redundant() -> None:
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in User.__table__.indexes
    }

    assert indexed_columns == {
        ("department_id",),
        ("manager_employee_no",),
        ("status",),
    }
    assert ("employee_no",) not in indexed_columns
