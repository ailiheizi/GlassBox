#!/usr/bin/env python3
"""
NewArch 端到端测试
测试完整的用户流程：注册 -> 登录 -> 使用各服务
"""

import requests
import time
import json
import sys
from typing import Optional
from dataclasses import dataclass

# 配置
BASE_URL = "http://localhost:8080"  # Gateway
INTERNAL_URLS = {
    "gateway": "http://localhost:8080",
    "auth": "http://localhost:3000/internal/auth",
    "memory": "http://localhost:3000/internal/memory",
    "index": "http://localhost:3000/internal/index",
    "browser": "http://localhost:3000/internal/browser",
    "task": "http://localhost:3000/internal/task",
    "ai": "http://localhost:3000/internal/ai",
}

@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    latency_ms: float

class E2ETest:
    def __init__(self):
        self.results: list[TestResult] = []
        self.token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.test_user = {
            "username": f"e2e_test_{int(time.time())}",
            "email": f"e2e_test_{int(time.time())}@test.com",
            "password": "test123456"
        }

    def run_test(self, name: str, func):
        """运行单个测试并记录结果"""
        start = time.time()
        try:
            result = func()
            latency = (time.time() - start) * 1000
            if result:
                self.results.append(TestResult(name, True, "OK", latency))
                print(f"  ✓ {name} ({latency:.0f}ms)")
                return True
            else:
                self.results.append(TestResult(name, False, "Failed", latency))
                print(f"  ✗ {name} ({latency:.0f}ms)")
                return False
        except Exception as e:
            latency = (time.time() - start) * 1000
            self.results.append(TestResult(name, False, str(e), latency))
            print(f"  ✗ {name}: {e} ({latency:.0f}ms)")
            return False

    # ==================== 健康检查测试 ====================

    def test_gateway_health(self) -> bool:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("status") == "ok"

    def test_auth_health(self) -> bool:
        resp = requests.get(f"{INTERNAL_URLS['auth']}/health", timeout=5)
        return resp.status_code == 200

    def test_memory_health(self) -> bool:
        resp = requests.get(f"{INTERNAL_URLS['memory']}/health", timeout=5)
        return resp.status_code == 200

    def test_index_health(self) -> bool:
        resp = requests.get(f"{INTERNAL_URLS['index']}/health", timeout=5)
        return resp.status_code == 200

    def test_browser_health(self) -> bool:
        resp = requests.get(f"{INTERNAL_URLS['browser']}/health", timeout=5)
        return resp.status_code == 200

    def test_task_health(self) -> bool:
        resp = requests.get(f"{INTERNAL_URLS['task']}/health", timeout=5)
        return resp.status_code == 200

    def test_ai_health(self) -> bool:
        resp = requests.get(f"{INTERNAL_URLS['ai']}/health", timeout=5)
        return resp.status_code == 200

    # ==================== 认证流程测试 ====================

    def test_register(self) -> bool:
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=self.test_user,
            timeout=10
        )
        return resp.status_code in [200, 201]

    def test_login(self) -> bool:
        resp = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={
                "username": self.test_user["username"],
                "password": self.test_user["password"]
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            self.token = data.get("token")
            self.user_id = data.get("user", {}).get("id")
            return self.token is not None
        return False

    def test_profile(self) -> bool:
        if not self.token:
            return False
        resp = requests.get(
            f"{BASE_URL}/api/v1/auth/profile",
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=10
        )
        return resp.status_code == 200

    # ==================== Memory 服务测试 ====================

    def test_memory_save(self) -> bool:
        if not self.token:
            return False
        resp = requests.post(
            f"{BASE_URL}/api/v1/memory/semantic",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-User-ID": self.user_id or ""
            },
            json={
                "content": "这是一条端到端测试的记忆内容",
                "content_type": "text"
            },
            timeout=30
        )
        return resp.status_code in [200, 201]

    def test_memory_search(self) -> bool:
        if not self.token:
            return False
        resp = requests.get(
            f"{BASE_URL}/api/v1/memory/semantic/search",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-User-ID": self.user_id or ""
            },
            params={"query": "测试", "limit": 5},
            timeout=30
        )
        return resp.status_code == 200

    # ==================== Index 服务测试 ====================

    def test_index_list(self) -> bool:
        if not self.token:
            return False
        resp = requests.get(
            f"{BASE_URL}/api/v1/indexes/ai",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-User-ID": self.user_id or ""
            },
            timeout=10
        )
        return resp.status_code == 200

    # ==================== Task 服务测试 ====================

    def test_task_list(self) -> bool:
        if not self.token:
            return False
        resp = requests.get(
            f"{BASE_URL}/api/v1/tasks",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-User-ID": self.user_id or ""
            },
            timeout=10
        )
        return resp.status_code == 200

    # ==================== AI 服务测试 ====================

    def test_ai_chat(self) -> bool:
        if not self.token:
            return False
        resp = requests.post(
            f"{INTERNAL_URLS['ai']}/chat",
            json={
                "messages": [{"role": "user", "content": "你好"}],
                "stream": False
            },
            timeout=60
        )
        return resp.status_code == 200

    def test_ai_embedding(self) -> bool:
        resp = requests.post(
            f"{INTERNAL_URLS['ai']}/embedding",
            json={"text": "测试文本"},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            return "embedding" in data and len(data["embedding"]) > 0
        return False

    # ==================== 运行所有测试 ====================

    def run_all(self):
        print("\n" + "=" * 60)
        print("NewArch 端到端测试")
        print("=" * 60)

        # 健康检查
        print("\n[1/5] 服务健康检查")
        self.run_test("Gateway Health", self.test_gateway_health)
        self.run_test("Auth Service Health", self.test_auth_health)
        self.run_test("Memory Service Health", self.test_memory_health)
        self.run_test("Index Service Health", self.test_index_health)
        self.run_test("Browser Service Health", self.test_browser_health)
        self.run_test("Task Service Health", self.test_task_health)
        self.run_test("AI Service Health", self.test_ai_health)

        # 认证流程
        print("\n[2/5] 认证流程测试")
        self.run_test("用户注册", self.test_register)
        self.run_test("用户登录", self.test_login)
        self.run_test("获取用户信息", self.test_profile)

        # Memory 服务
        print("\n[3/5] Memory 服务测试")
        self.run_test("保存记忆", self.test_memory_save)
        self.run_test("搜索记忆", self.test_memory_search)

        # Index 和 Task 服务
        print("\n[4/5] Index/Task 服务测试")
        self.run_test("获取索引列表", self.test_index_list)
        self.run_test("获取任务列表", self.test_task_list)

        # AI 服务
        print("\n[5/5] AI 服务测试")
        self.run_test("AI 对话", self.test_ai_chat)
        self.run_test("AI Embedding", self.test_ai_embedding)

        # 汇总结果
        self.print_summary()

    def print_summary(self):
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)
        avg_latency = sum(r.latency_ms for r in self.results) / total if total > 0 else 0

        print(f"\n总计: {total} 测试")
        print(f"通过: {passed} ✓")
        print(f"失败: {failed} ✗")
        print(f"平均延迟: {avg_latency:.0f}ms")
        print(f"通过率: {passed/total*100:.1f}%")

        if failed > 0:
            print("\n失败的测试:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        print("\n" + "=" * 60)

        return failed == 0


if __name__ == "__main__":
    test = E2ETest()
    success = test.run_all()
    sys.exit(0 if success else 1)
