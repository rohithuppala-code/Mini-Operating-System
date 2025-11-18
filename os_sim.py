#!/usr/bin/env python3
"""
OS Simulator (interactive).

Features (9):
1. Create Process
2. Kill Process
3. Show Process Table
4. Run Scheduler (MLFQ with Round-Robin per queue)
5. Block/Unblock Process (I/O simulation)
6. Allocate Memory (simple contiguous allocation)
7. Free Memory
8. File Create/Write/Read (very simple in-memory FS)
9. Exit
"""

import time
import queue
import itertools
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ---------- Data structures ----------
_pid_counter = itertools.count(1)

@dataclass
class Process:
    pid: int
    name: str
    burst: int              # total CPU burst time (remaining)
    original_burst: int
    priority: int           # user hint (not used by MLFQ directly)
    state: str = "READY"    # READY, RUNNING, BLOCKED, TERMINATED
    memory_block: Optional[tuple] = None  # (start, size)
    io_wait: int = 0        # turns remaining in I/O
    arrived_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    last_queue_level: int = 0  # MLFQ level last executed

# Simple in-memory file system
file_system: Dict[str, bytes] = {}

# Simple memory manager (contiguous free list)
MEMORY_SIZE = 1024  # units
memory_free_list = [(0, MEMORY_SIZE)]  # list of (start, size)

# Process tables and MLFQ queues
process_table: Dict[int, Process] = {}
READY_QUEUES = [queue.Queue(), queue.Queue(), queue.Queue()]  # level 0 (highest) to 2 (lowest)
BLOCKED_LIST: List[int] = []

# MLFQ configuration: quantum per level
QUANTA = [4, 8, 16]

# ---------- Utilities ----------
def allocate_memory(size:int):
    """First-fit allocation from free list. Returns (start, size) or None."""
    global memory_free_list
    for i, (start, sz) in enumerate(memory_free_list):
        if sz >= size:
            alloc = (start, size)
            if sz == size:
                memory_free_list.pop(i)
            else:
                memory_free_list[i] = (start + size, sz - size)
            return alloc
    return None

def free_memory(block):
    """Free a block and coalesce."""
    global memory_free_list
    if block is None:
        return
    memory_free_list.append(block)
    memory_free_list.sort()
    # coalesce
    merged = []
    cur_start, cur_sz = memory_free_list[0]
    for s, sz in memory_free_list[1:]:
        if cur_start + cur_sz == s:
            cur_sz += sz
        else:
            merged.append((cur_start, cur_sz))
            cur_start, cur_sz = s, sz
    merged.append((cur_start, cur_sz))
    memory_free_list = merged

def print_memory_state():
    print("Memory free blocks:", memory_free_list)

# ---------- Feature implementations ----------
def create_process(name:str, burst:int, priority:int):
    pid = next(_pid_counter)
    p = Process(pid=pid, name=name, burst=burst, original_burst=burst, priority=priority)
    process_table[pid] = p
    # insert into highest priority ready queue
    READY_QUEUES[0].put(pid)
    print(f"[CREATE] PID={pid} Name={name} Burst={burst} Priority={priority}")
    return pid

def kill_process(pid:int):
    p = process_table.get(pid)
    if not p:
        print("[KILL] No such PID")
        return False
    p.state = "TERMINATED"
    p.finished_at = time.time()
    # free memory if any
    if p.memory_block:
        free_memory(p.memory_block)
        p.memory_block = None
    # remove from blocked list if present
    if pid in BLOCKED_LIST:
        BLOCKED_LIST.remove(pid)
    print(f"[KILL] PID={pid} terminated and resources freed.")
    return True

def show_process_table():
    print("PID | Name     | State    | RemainingBurst | Priority | MemBlock       | IOwait")
    for pid, p in sorted(process_table.items()):
        print(f"{pid:3} | {p.name:8} | {p.state:8} | {p.burst:14} | {p.priority:8} | {str(p.memory_block):13} | {p.io_wait}")

def block_process(pid:int, io_time:int=3):
    p = process_table.get(pid)
    if not p:
        print("[BLOCK] No such PID")
        return False
    if p.state == "TERMINATED":
        print("[BLOCK] Process already terminated")
        return False
    p.state = "BLOCKED"
    p.io_wait = io_time
    BLOCKED_LIST.append(pid)
    print(f"[BLOCK] PID={pid} blocked for I/O ({io_time} ticks).")
    return True

def unblock_tick():
    """Decrement I/O waits and move to ready when done."""
    for pid in list(BLOCKED_LIST):
        p = process_table.get(pid)
        if not p:
            BLOCKED_LIST.remove(pid)
            continue
        p.io_wait -= 1
        if p.io_wait <= 0:
            p.state = "READY"
            BLOCKED_LIST.remove(pid)
            READY_QUEUES[0].put(pid)
            print(f"[IO] PID={pid} I/O complete, moved to ready (level 0).")

def allocate_memory_to_process(pid:int, size:int):
    p = process_table.get(pid)
    if not p:
        print("[ALLOC] No such PID")
        return False
    if p.memory_block:
        print("[ALLOC] Process already has memory allocated:", p.memory_block)
        return False
    block = allocate_memory(size)
    if not block:
        print("[ALLOC] Not enough memory")
        return False
    p.memory_block = block
    print(f"[ALLOC] PID={pid} allocated memory {block}")
    return True

def free_memory_of_process(pid:int):
    p = process_table.get(pid)
    if not p:
        print("[FREE] No such PID")
        return False
    if not p.memory_block:
        print("[FREE] Process has no memory allocated")
        return False
    free_memory(p.memory_block)
    print(f"[FREE] Freed memory {p.memory_block} of PID={pid}")
    p.memory_block = None
    return True

def fs_create(filename:str, data:bytes=b""):
    if filename in file_system:
        print("[FS] File already exists, overwriting.")
    file_system[filename] = data
    print(f"[FS] Created/updated file '{filename}' ({len(data)} bytes)")

def fs_read(filename:str):
    data = file_system.get(filename)
    if data is None:
        print("[FS] No such file")
        return None
    print(f"[FS] Read file '{filename}' ({len(data)} bytes)")
    return data

# ---------- Scheduler (MLFQ with RR) ----------
def run_scheduler(verbose=True, max_ticks=1000):
    """
    Run scheduler until no ready processes or max_ticks reached.
    On each tick: pick from highest non-empty queue; run for up to quantum or until process blocks/finishes.
    """
    tick = 0
    stats = {}
    while tick < max_ticks:
        # handle I/O unblock
        unblock_tick()

        # find highest non-empty ready queue
        pid = None
        level = None
        for i, q in enumerate(READY_QUEUES):
            if not q.empty():
                try:
                    pid = q.get_nowait()
                except queue.Empty:
                    continue
                level = i
                break
        if pid is None:
            if verbose:
                print("[SCHED] No ready processes. Scheduler idle.")
            break

        p = process_table.get(pid)
        if not p or p.state == "TERMINATED":
            continue

        quantum = QUANTA[level]
        run_time = min(quantum, p.burst)
        p.state = "RUNNING"
        if verbose:
            print(f"[TICK {tick}] Running PID={pid} at level={level} for up to {run_time} ticks (quantum={quantum}).")

        # simulate run (tick by tick)
        for r in range(run_time):
            tick += 1
            p.burst -= 1
            # for demo: small chance to block on I/O
            if random.random() < 0.05:
                p.state = "BLOCKED"
                p.io_wait = random.randint(2,5)
                BLOCKED_LIST.append(pid)
                if verbose:
                    print(f"[TICK {tick}] PID={pid} blocked for I/O (will wait {p.io_wait}).")
                break
            if p.burst <= 0:
                p.state = "TERMINATED"
                p.finished_at = time.time()
                if p.memory_block:
                    free_memory(p.memory_block)
                    p.memory_block = None
                if verbose:
                    print(f"[TICK {tick}] PID={pid} finished execution.")
                break

        # requeue or demote if needed
        if p.state == "READY":
            new_level = min(2, level + 1)
            READY_QUEUES[new_level].put(pid)
            p.last_queue_level = new_level
            if verbose:
                print(f"[TICK {tick}] PID={pid} quantum expired; demoted to level {new_level}.")
        elif p.state == "RUNNING":
            if p.burst > 0:
                p.state = "READY"
                new_level = min(2, level + 1)
                READY_QUEUES[new_level].put(pid)
                p.last_queue_level = new_level
                if verbose:
                    print(f"[TICK {tick}] PID={pid} quantum expired; demoted to level {new_level}.")
            else:
                p.state = "TERMINATED"
                p.finished_at = time.time()
                if p.memory_block:
                    free_memory(p.memory_block)
                    p.memory_block = None

        # collect stats for terminated processes
        for proc in list(process_table.values()):
            if proc.state == "TERMINATED" and proc.pid not in stats:
                turnaround = (proc.finished_at - proc.arrived_at) if proc.finished_at else 0
                stats[proc.pid] = {'turnaround': turnaround, 'name': proc.name, 'original_burst': proc.original_burst}

    if verbose:
        print("[SCHED] Scheduler finished. Stats:")
        for pid, s in stats.items():
            print(f"PID={pid} Name={s['name']} Turnaround~{s['turnaround']:.2f}s Burst={s['original_burst']}")
    return stats

# ---------- Interactive CLI ----------
def interactive():
    print("=== Simple OS Simulator ===")
    menu_lines = [
        "Choose an option:",
        "1) Create Process",
        "2) Kill Process",
        "3) Show Process Table",
        "4) Run Scheduler (MLFQ)",
        "5) Block Process (I/O) / Unblock handled by scheduler",
        "6) Allocate Memory to Process",
        "7) Free Memory of Process",
        "8) File System: create/write/read file",
        "9) Exit",
    ]
    menu = "\n".join(menu_lines) + "\n"
    while True:
        print(menu)
        try:
            choice = int(input("Enter choice [1-9]: ").strip())
        except Exception:
            print("Invalid input.")
            continue
        if choice == 1:
            name = input("Process name: ").strip() or "proc"
            burst = int(input("CPU burst (units): ").strip() or "10")
            pr = int(input("Priority (int, hint): ").strip() or "0")
            create_process(name, burst, pr)
        elif choice == 2:
            pid = int(input("PID to kill: ").strip())
            kill_process(pid)
        elif choice == 3:
            show_process_table()
            print_memory_state()
        elif choice == 4:
            max_ticks = int(input("Max ticks to run (e.g., 200): ").strip() or "200")
            run_scheduler(verbose=True, max_ticks=max_ticks)
        elif choice == 5:
            pid = int(input("PID to block: ").strip())
            io_t = int(input("I/O wait ticks: ").strip() or "3")
            block_process(pid, io_t)
        elif choice == 6:
            pid = int(input("PID to alloc memory to: ").strip())
            size = int(input("Size units to allocate: ").strip() or "64")
            allocate_memory_to_process(pid, size)
        elif choice == 7:
            pid = int(input("PID to free memory of: ").strip())
            free_memory_of_process(pid)
        elif choice == 8:
            sub = input("Create(C) / Read(R): ").strip().upper()
            if sub == 'C':
                fname = input("Filename: ").strip()
                content = input("Content string: ")
                fs_create(fname, content.encode('utf-8'))
            elif sub == 'R':
                fname = input("Filename: ").strip()
                data = fs_read(fname)
                if data is not None:
                    print(data.decode('utf-8', errors='replace'))
            else:
                print("Unknown FS option.")
        elif choice == 9:
            print("Exiting simulator.")
            break
        else:
            print("Unknown choice.")

if __name__ == "__main__":
    interactive()
