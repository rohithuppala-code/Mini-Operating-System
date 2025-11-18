# OS Simulator

An interactive operating system simulator implementing process scheduling, memory management, and a simple file system.

## Overview

This project simulates core OS concepts including multi-level feedback queue (MLFQ) scheduling, contiguous memory allocation, process management, and basic file operations.

## Features

- **Process Management** - Create, kill, and monitor processes
- **MLFQ Scheduler** - Multi-Level Feedback Queue with Round-Robin scheduling
- **Memory Management** - Contiguous memory allocation with first-fit algorithm
- **I/O Simulation** - Block/unblock processes for I/O operations
- **File System** - Simple in-memory file creation and reading
- **Interactive CLI** - Menu-driven interface for all operations

## Requirements

- Python 3.7+
- No external dependencies

## Installation

```bash
git clone <repository-url>
cd <repository-name>
```

## Usage

Run the simulator:

```bash
python3 os_simulator.py
```

### Menu Options

1. **Create Process** - Add a new process with specified CPU burst and priority
2. **Kill Process** - Terminate a process and free its resources
3. **Show Process Table** - Display all processes and memory state
4. **Run Scheduler** - Execute MLFQ scheduler for specified ticks
5. **Block Process** - Simulate I/O blocking for a process
6. **Allocate Memory** - Assign memory block to a process
7. **Free Memory** - Release memory allocated to a process
8. **File System** - Create/write or read files
9. **Exit** - Quit the simulator

## Scheduling Algorithm

**Multi-Level Feedback Queue (MLFQ)**
- 3 priority levels (0 = highest, 2 = lowest)
- Time quantum per level: [4, 8, 16] ticks
- Processes demote to lower priority after using their quantum
- I/O-blocked processes return to highest priority when ready

## Memory Management

- Total memory: 1024 units
- First-fit allocation strategy
- Automatic coalescing of free blocks
- Memory freed automatically when process terminates

## Example Session

```bash
=== Simple OS Simulator ===
Choose an option:
1) Create Process
...
Enter choice [1-9]: 1
Process name: test_proc
CPU burst (units): 20
Priority (int, hint): 0
[CREATE] PID=1 Name=test_proc Burst=20 Priority=0

Enter choice [1-9]: 6
PID to alloc memory to: 1
Size units to allocate: 64
[ALLOC] PID=1 allocated memory (0, 64)

Enter choice [1-9]: 4
Max ticks to run (e.g., 200): 50
[TICK 0] Running PID=1 at level=0 for up to 4 ticks (quantum=4).
[TICK 4] PID=1 quantum expired; demoted to level 1.
...
```

## Implementation Details

**Process States:**
- READY - In ready queue waiting for CPU
- RUNNING - Currently executing
- BLOCKED - Waiting for I/O
- TERMINATED - Finished execution

**Data Structures:**
- Process table (dictionary)
- 3-level ready queues
- Blocked process list
- Free memory list with coalescing

## Educational Purpose

This simulator demonstrates:
- Process lifecycle management
- CPU scheduling algorithms
- Memory allocation strategies
- Basic file system operations
- I/O handling and blocking

