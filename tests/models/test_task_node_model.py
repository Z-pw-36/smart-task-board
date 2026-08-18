from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    inspect,
)

from app.models import (
    Task,
    TaskNode,
    TaskNodeDependency,
    TaskNodeParticipant,
    User,
)

TASK_NODE_FIELDS = {
    "node_id",
    "task_id",
    "node_order",
    "sort_weight",
    "node_name",
    "action_detail",
    "tools_or_materials",
    "owner_employee_no",
    "planned_start_time",
    "planned_deadline",
    "estimated_hours",
    "actual_hours",
    "deliverable",
    "acceptance_criteria",
    "progress_percent",
    "status",
    "completed_at",
}


def test_task_node_columns_and_primary_key_contract() -> None:
    table = TaskNode.__table__

    assert table.name == "task_nodes"
    assert set(table.columns.keys()) == TASK_NODE_FIELDS
    assert len(TASK_NODE_FIELDS) == 17
    assert [column.name for column in table.primary_key.columns] == ["node_id"]
    assert isinstance(table.c.node_id.type, Uuid)
    assert table.c.node_id.default is not None
    assert table.c.node_id.default.is_callable
    for forbidden_field in (
        "id",
        "user_id",
        "employee_id",
        "minimum_result",
        "blocked_reason",
        "created_at",
        "updated_at",
    ):
        assert forbidden_field not in table.columns


def test_task_node_foreign_keys_nullability_and_string_contract() -> None:
    table = TaskNode.__table__
    task_foreign_key = next(iter(table.c.task_id.foreign_keys))
    owner_foreign_key = next(iter(table.c.owner_employee_no.foreign_keys))

    assert task_foreign_key.target_fullname == "tasks.task_id"
    assert task_foreign_key.ondelete == "RESTRICT"
    assert table.c.task_id.nullable is False
    assert owner_foreign_key.target_fullname == "users.employee_no"
    assert owner_foreign_key.ondelete == "RESTRICT"
    assert table.c.owner_employee_no.nullable is True
    for field_name in (
        "node_name",
        "action_detail",
        "tools_or_materials",
        "owner_employee_no",
        "deliverable",
        "acceptance_criteria",
        "status",
    ):
        assert isinstance(table.c[field_name].type, String)
        assert table.c[field_name].type.length is None
    assert table.c.node_name.nullable is False
    assert table.c.action_detail.nullable is True
    assert table.c.tools_or_materials.nullable is True
    assert table.c.deliverable.nullable is True
    assert table.c.acceptance_criteria.nullable is True


def test_task_node_types_defaults_and_check_constraints() -> None:
    table = TaskNode.__table__
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert isinstance(table.c.node_order.type, Integer)
    assert table.c.node_order.nullable is False
    assert isinstance(table.c.sort_weight.type, Integer)
    assert table.c.sort_weight.default.arg == 0
    assert isinstance(table.c.estimated_hours.type, Numeric)
    assert isinstance(table.c.actual_hours.type, Numeric)
    assert table.c.estimated_hours.type.precision is None
    assert table.c.actual_hours.type.scale is None
    assert isinstance(table.c.progress_percent.type, Integer)
    assert table.c.progress_percent.default.arg == 0
    assert isinstance(table.c.status.type, String)
    assert table.c.status.default.arg == "pending"
    assert set(checks) == {
        "ck_task_nodes_actual_hours_non_negative",
        "ck_task_nodes_estimated_hours_non_negative",
        "ck_task_nodes_node_order_positive",
        "ck_task_nodes_planned_time_order",
        "ck_task_nodes_progress_percent_range",
    }
    assert "node_order >= 1" in checks["ck_task_nodes_node_order_positive"]
    assert "estimated_hours >= 0" in checks[
        "ck_task_nodes_estimated_hours_non_negative"
    ]
    assert "actual_hours >= 0" in checks[
        "ck_task_nodes_actual_hours_non_negative"
    ]
    assert "progress_percent >= 0" in checks[
        "ck_task_nodes_progress_percent_range"
    ]
    assert "progress_percent <= 100" in checks[
        "ck_task_nodes_progress_percent_range"
    ]
    assert "planned_deadline >= planned_start_time" in checks[
        "ck_task_nodes_planned_time_order"
    ]


def test_task_node_time_columns_are_timezone_aware() -> None:
    table = TaskNode.__table__

    for field_name in ("planned_start_time", "planned_deadline", "completed_at"):
        column = table.c[field_name]
        assert isinstance(column.type, DateTime)
        assert column.type.timezone is True
        assert column.nullable is True


def test_task_node_unique_constraint_and_indexes() -> None:
    table = TaskNode.__table__
    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexed_columns = {
        tuple(column.name for column in index.columns) for index in table.indexes
    }

    assert unique_constraints == {("task_id", "node_id")}
    assert indexed_columns == {
        ("owner_employee_no",),
        ("planned_deadline",),
        ("status",),
        ("task_id", "node_order", "sort_weight"),
    }
    assert ("task_id", "node_order") not in unique_constraints


def test_task_node_relationships_are_bidirectional_and_safe() -> None:
    relationships = inspect(TaskNode).relationships

    assert set(relationships.keys()) == {
        "incoming_dependencies",
        "outgoing_dependencies",
        "owner",
        "participants",
        "task",
    }
    assert relationships.task.back_populates == "nodes"
    assert relationships.task.mapper.class_ is Task
    assert relationships.owner.back_populates == "owned_task_nodes"
    assert relationships.owner.mapper.class_ is User
    assert relationships.outgoing_dependencies.back_populates == "predecessor_node"
    assert relationships.outgoing_dependencies.mapper.class_ is TaskNodeDependency
    assert relationships.incoming_dependencies.back_populates == "successor_node"
    assert relationships.incoming_dependencies.mapper.class_ is TaskNodeDependency
    assert relationships.participants.back_populates == "node"
    assert relationships.participants.mapper.class_ is TaskNodeParticipant

    for relationship in relationships:
        assert "delete" not in relationship.cascade
        assert "delete-orphan" not in relationship.cascade
