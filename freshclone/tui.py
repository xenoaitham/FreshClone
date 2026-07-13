from __future__ import annotations

import collections
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.table import Table

class FreshcloneTUI:
    def __init__(self, steps: list):
        self.steps = steps
        self.log_lines = collections.deque(maxlen=30)
        self.step_status = {s.index: "pending" for s in steps}
        self.current_step = None
        
        self.layout = Layout()
        self.layout.split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2)
        )
    
    def update_step(self, step_index: int, status: str):
        self.step_status[step_index] = status
        if status == "running":
            self.current_step = step_index
            self.log_lines.clear()
            
    def add_log(self, line: str):
        self.log_lines.append(line.rstrip())
        # Auto-advance first pending step to running when logs arrive
        for step in self.steps:
            if self.step_status.get(step.index) == "pending":
                self.update_step(step.index, "running")
                break
        
    def generate(self) -> Layout:
        # Build checklist table
        table = Table(show_header=False, box=None, padding=(0, 1))
        for step in self.steps:
            status = self.step_status.get(step.index, "skipped")
            
            if status == "pending":
                icon = "[dim]○[/dim]"
                style = "dim"
            elif status == "running":
                icon = "[yellow]●[/yellow]"
                style = "yellow bold"
            elif status == "passed":
                icon = "[green]✔[/green]"
                style = "green"
            elif status == "failed":
                icon = "[red]✖[/red]"
                style = "red bold"
            else:
                icon = "[dim]⏭[/dim]"
                style = "dim"
                
            label = step.command.splitlines()[0] if step.command else "Unknown"
            if len(label) > 40:
                label = label[:37] + "..."
            table.add_row(icon, f"[{style}]{label}[/{style}]")
            
        self.layout["left"].update(Panel(table, title="[bold]Steps[/bold]", border_style="blue"))
        
        # Build logs view
        log_text = Text("\n".join(self.log_lines))
        title = f"[bold]Logs: Step {self.current_step}[/bold]" if self.current_step else "[bold]Logs[/bold]"
        self.layout["right"].update(Panel(log_text, title=title, border_style="green"))
        
        return self.layout
