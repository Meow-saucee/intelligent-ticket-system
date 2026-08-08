from __future__ import annotations

from dataclasses import dataclass

from .domain import Category, Priority, Status


@dataclass(frozen=True)
class SeedTicket:
    key: str
    title: str
    description: str
    submitter: str
    priority: Priority
    category: Category
    status: Status


SAMPLE_TICKETS = (
    SeedTicket(
        "sample-001",
        "邮箱无法登录",
        "密码正确但登录失败。",
        "alice",
        Priority.P1,
        Category.ACCOUNT_ACCESS,
        Status.NEW,
    ),
    SeedTicket(
        "sample-002",
        "办公软件启动失败",
        "更新后无法启动办公软件。",
        "bob",
        Priority.P2,
        Category.SOFTWARE,
        Status.TRIAGED,
    ),
    SeedTicket(
        "sample-003",
        "办公网络中断",
        "三楼办公区无法访问内网。",
        "carol",
        Priority.P0,
        Category.NETWORK,
        Status.IN_PROGRESS,
    ),
    SeedTicket(
        "sample-004",
        "笔记本无法充电",
        "电源适配器连接后电量没有增加。",
        "david",
        Priority.P3,
        Category.HARDWARE,
        Status.RESOLVED,
    ),
    SeedTicket(
        "sample-005",
        "会议室空调温度异常",
        "会议室空调持续制冷。",
        "erin",
        Priority.P2,
        Category.FACILITIES,
        Status.CLOSED,
    ),
)
