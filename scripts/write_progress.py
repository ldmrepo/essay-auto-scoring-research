"""Phase 3 operations C5: 학습 스크립트 progress.json 헬퍼 (Hard Rule #17).

사용 예 (pipelines/train_transformer.py 또는 vast.ai 학습 스크립트):

    from scripts.write_progress import ProgressWriter

    progress = ProgressWriter(
        path="/workspace/progress.json",
        task_id="T-CYCLE-M2-MODEL",
        model_id="M5",
        total_steps=15,
    )

    for fold_idx in range(5):
        for epoch_idx in range(3):
            step_idx = fold_idx * 3 + epoch_idx
            progress.update(
                current_step=f"fold_{fold_idx}_epoch_{epoch_idx}",
                current_step_idx=step_idx,
                last_checkpoint_path=str(ckpt_path),
            )
            ... training ...
            progress.record_metric(f"fold_{fold_idx}_epoch_{epoch_idx}_qwk", qwk)

    progress.mark_done()

deploy:
    - 로컬 학습: `scripts/`가 PYTHONPATH에 있어야 함 (`pip install -e .` 또는 PYTHONPATH=.)
    - vast.ai bootstrap: rsync 또는 scp로 scripts/__init__.py + write_progress.py 동반 전송 권장
    - import 실패 시 NOP fallback은 _maybe_progress() 헬퍼 (학습 실패 방지)

변경 이력:
- v2 (2026-05-28): T2-15 + T3-20 + R3-F8/F9/F18/F26 fix
  - scripts/__init__.py 동반 (패키지 import 가능)
  - _read_gpu_util / _read_gpu_mem 실제 구현 (nvidia-smi 파싱)
  - ETA max(0, ...) + 최소 갱신 간격
  - tmp 파일 PID suffix (multi-worker race 회피)
  - .json 확장자 강제 (with_suffix 정확성)
  - _maybe_progress() NOP fallback
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


class ProgressWriter:
    """주기적 progress.json 갱신. Phase 3 Hard Rule #17 준수.

    atomic write 보장 (tmp → rename), polling 측 partial read 방지.
    동시 multi-worker write 시 tmp 파일 PID suffix로 race 회피.
    """

    REQUIRED_FIELDS = (
        "task_id",
        "model_id",
        "started_at",
        "current_step",
        "total_steps",
        "current_step_idx",
        "metrics_so_far",
        "gpu_util_pct",
        "gpu_mem_used_mb",
        "elapsed_sec",
        "eta_sec",
        "last_checkpoint_path",
        "last_updated",
    )

    def __init__(
        self,
        path: str | os.PathLike,
        task_id: str,
        model_id: str,
        total_steps: int = 0,
        min_flush_interval_sec: float = 5.0,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._t0 = time.time()
        self._last_flush_t = 0.0
        self._min_flush_interval = float(min_flush_interval_sec)
        self.state: dict[str, Any] = {
            "task_id": task_id,
            "model_id": model_id,
            "started_at": _now_iso(),
            "current_step": "init",
            "total_steps": int(total_steps),
            "current_step_idx": 0,
            "metrics_so_far": {},
            "gpu_util_pct": None,
            "gpu_mem_used_mb": None,
            "elapsed_sec": 0,
            "eta_sec": None,
            "last_checkpoint_path": None,
            "last_updated": _now_iso(),
        }
        self._flush(force=True)

    def update(self, force: bool = False, **kwargs: Any) -> None:
        """주요 진행 상태 필드 갱신 + atomic write (rate-limited)."""
        self.state.update(kwargs)
        self.state["elapsed_sec"] = int(time.time() - self._t0)
        self.state["last_updated"] = _now_iso()
        # GPU util 자동 채움 (인자로 명시 안 주면 nvidia-smi 시도)
        if "gpu_util_pct" not in kwargs:
            util, mem = _read_gpu_stats()
            if util is not None:
                self.state["gpu_util_pct"] = util
            if mem is not None:
                self.state["gpu_mem_used_mb"] = mem
        # ETA 계산: total_steps > 0 + current_step_idx > 0 시
        idx = self.state.get("current_step_idx", 0)
        total = self.state.get("total_steps", 0)
        if total and isinstance(idx, int) and idx > 0:
            elapsed = self.state["elapsed_sec"]
            try:
                eta = int(elapsed * (total - idx) / idx)
                self.state["eta_sec"] = max(0, eta)  # R3-F9: 음수 방지
            except ZeroDivisionError:
                self.state["eta_sec"] = None
        self._flush(force=force)

    def record_metric(self, key: str, value: Any) -> None:
        """metrics_so_far[key] = value + atomic write."""
        self.state["metrics_so_far"][key] = value
        self.update()

    def mark_done(self) -> None:
        """DONE marker 생성 (polling 측 종료 감지)."""
        self.update(
            force=True,
            current_step="done",
            current_step_idx=self.state.get("total_steps", 0),
        )
        done_marker = self.path.parent / "DONE"
        done_marker.write_text(_now_iso())

    def mark_fail(self, reason: str) -> None:
        """FAIL marker 생성 (polling 측 실패 감지)."""
        self.update(force=True, current_step=f"fail: {reason}")
        fail_marker = self.path.parent / "FAIL"
        fail_marker.write_text(f"{_now_iso()}\n{reason}\n")

    def _flush(self, force: bool = False) -> None:
        """Atomic write to self.path (rate-limited unless force=True)."""
        now = time.time()
        if not force and (now - self._last_flush_t) < self._min_flush_interval:
            return
        # T2-15/R3-F26: .json 확장자 강제 (with_suffix 입력 무관)
        # R3-F18: tmp 파일 PID suffix (multi-worker race 회피)
        tmp = self.path.with_name(f"{self.path.stem}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2))
        os.replace(tmp, self.path)
        self._last_flush_t = now


def _read_gpu_stats() -> tuple[int | None, int | None]:
    """nvidia-smi로 (gpu_util_pct, gpu_mem_used_mb) 반환. 실패 시 (None, None).

    R3-F21 + T3-20: GPU util 0% 진단 핵심 헬퍼.
    R3-NF1 fix (multi-GPU): CUDA_VISIBLE_DEVICES 환경변수가 있으면 그 GPU의 stats만,
        없으면 모든 GPU의 max util + total mem 반환 (학습 GPU가 1번이어도 검출 가능).
    """
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu,memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            return None, None
        lines = [line.strip() for line in out.stdout.strip().splitlines() if line.strip()]
        if not lines:
            return None, None

        # 각 GPU의 (index, util, mem) 파싱
        gpu_stats: list[tuple[int, int, int]] = []
        for line in lines:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit() and parts[2].isdigit():
                gpu_stats.append((int(parts[0]), int(parts[1]), int(parts[2])))

        if not gpu_stats:
            return None, None

        # R3-NF1 fix: CUDA_VISIBLE_DEVICES가 명시되면 그 GPU만 집계
        visible = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
        if visible and visible != "":
            try:
                visible_ids = {int(x.strip()) for x in visible.split(",") if x.strip().isdigit()}
                gpu_stats = [(i, u, m) for i, u, m in gpu_stats if i in visible_ids]
                if not gpu_stats:
                    return None, None
            except ValueError:
                pass

        # multi-GPU: max util (학습 active GPU 검출) + total mem
        max_util = max(u for _, u, _ in gpu_stats)
        total_mem = sum(m for _, _, m in gpu_stats)
        return max_util, total_mem
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
        return None, None


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _maybe_progress(*args, **kwargs) -> "ProgressWriter | None":
    """학습 스크립트에서 import 실패 가드 패턴 (R3-F8 fallback).

    사용:
        try:
            from scripts.write_progress import _maybe_progress
            progress = _maybe_progress(...)
        except ImportError:
            progress = None
        ...
        if progress: progress.update(...)
    """
    try:
        return ProgressWriter(*args, **kwargs)
    except Exception:  # noqa: BLE001
        return None
