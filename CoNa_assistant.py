import tkinter as tk
from tkinter import simpledialog, colorchooser, messagebox, filedialog, ttk
from PIL import Image, ImageTk  # Pillow for image handling
import json, os, datetime

# Constants
GRID_SIZE = 999    # 999x999 grid
CELL_SIZE = 10     # Default cell size
DEFAULT_START_COORDINATE = (GRID_SIZE // 2, GRID_SIZE // 2)

class GridApp:
    def __init__(self, root, start_coordinate=DEFAULT_START_COORDINATE):
        self.root = root
        self.set_window_title(self.root, "CosaNation's management assistant")
        
        # Grid settings
        self.minor_grid_color = "#D3D3D3"
        self.major_grid_color = "black"
        self.grid_zoom_threshold = 2
        self.minor_opacity = 100
        self.major_opacity = 100
        self.dark_mode = False

        # Alliance members and defaults
        self.alliance_members = []
        self.alliance_default_colors = {
            "R1": "#2C3E50",
            "R2": "#34495E",
            "R3": "#5D6D7E",
            "R4": "#2874A6",
            "R5": "#1F618D"
        }
        self.alliance_members_changed = False
        self.load_alliance_members()  # NEW: load alliance members from file
        self.predefined_vs_tasks = ["Daily Check", "System Update", "Report Generation"]

        # Schedule data: each day will have two fixed items: Conductor and VS.
        self.conductor_assignments = {}  # e.g., {"2025-03-18": "Alice", ...}
        self.vs_tasks = {}               # e.g., {"2025-03-18": ["Task 1", "Task 2"], ...}
        self.vs_tasks_by_weekday = {}  # Keys are weekday names (e.g., "Monday")
        self.predefined_vs_tasks = ["Daily Check", "System Update", "Report Generation"]
        self.vs_task_exceptions = {}  # Keys: date (YYYY-MM-DD), value: list of recurring tasks to exclude for that day
      
        # Canvas, zoom, panning, and grid objects
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.is_panning = False
        self.placed_objects = {}
        self.terrain_cells = {}

        # Load textures for terrain
        self.load_textures()

        self.start_coordinate = start_coordinate
        self.set_start_position(*self.start_coordinate)

        # Create UI elements
        self.create_ui()

        # Load saved state and start autosave loop
        self.load_state()
        self.load_weekly_schedule()
        self.draw_grid()
        self.autosave()

        # Load preset terrain (if no saved state)
        self.initialize_preset_terrain()

    # ------------------------------
    # Alliance Members Loading
    # ------------------------------
    def load_alliance_members(self):
        """Loads alliance members from 'alliance_members.txt' if it exists."""
        if os.path.exists("alliance_members.txt"):
            with open("alliance_members.txt", "r") as f:
                try:
                    self.alliance_members = json.load(f)
                except Exception as e:
                    print("Error loading alliance members:", e)
                    self.alliance_members = []
        else:
            self.alliance_members = []

    # ------------------------------
    # Standard Grid, Zoom, and Panning Functions
    # ------------------------------
    def edit_grid_properties(self):
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Grid Properties")
        dark_mode_var = tk.BooleanVar(value=self.dark_mode)
        tk.Checkbutton(
            settings_win, text="Enable Dark Mode", variable=dark_mode_var,
            command=lambda: self.update_dark_mode(dark_mode_var.get())
        ).grid(row=0, column=0, columnspan=2, pady=5)
        tk.Label(settings_win, text="Minor Grid Color:").grid(row=1, column=0, sticky="w")
        tk.Button(
            settings_win, text="Choose Minor Color", command=lambda: self.choose_grid_color("minor")
        ).grid(row=1, column=1, padx=5, pady=5)
        tk.Label(settings_win, text="Minor Grid Opacity:").grid(row=2, column=0, sticky="w")
        minor_opacity_scale = tk.Scale(
            settings_win, from_=0, to=100, orient="horizontal",
            command=lambda val: self.update_grid_opacity("minor", val)
        )
        minor_opacity_scale.set(self.minor_opacity)
        minor_opacity_scale.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        tk.Label(settings_win, text="Major Grid Color:").grid(row=3, column=0, sticky="w")
        tk.Button(
            settings_win, text="Choose Major Color", command=lambda: self.choose_grid_color("major")
        ).grid(row=3, column=1, padx=5, pady=5)
        tk.Label(settings_win, text="Major Grid Opacity:").grid(row=4, column=0, sticky="w")
        major_opacity_scale = tk.Scale(
            settings_win, from_=0, to=100, orient="horizontal",
            command=lambda val: self.update_grid_opacity("major", val)
        )
        major_opacity_scale.set(self.major_opacity)
        major_opacity_scale.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
        tk.Label(settings_win, text="Grid Zoom Threshold (cell size):").grid(row=5, column=0, sticky="w")
        zoom_threshold_scale = tk.Scale(
            settings_win, from_=0, to=10, resolution=0.1, orient="horizontal",
            command=lambda val: self.update_zoom_threshold(val)
        )
        zoom_threshold_scale.set(self.grid_zoom_threshold)
        zoom_threshold_scale.grid(row=5, column=1, sticky="ew", padx=5, pady=5)
        tk.Button(settings_win, text="Close", command=settings_win.destroy).grid(row=6, column=0, columnspan=2, pady=10)

    def update_zoom_threshold(self, val):
        self.grid_zoom_threshold = float(val)
        self.draw_grid()

    def choose_grid_color(self, type):
        color = colorchooser.askcolor(title=f"Choose {type.capitalize()} Grid Color")[1]
        if color:
            if type == "minor":
                self.minor_grid_color = color
            elif type == "major":
                self.major_grid_color = color
            self.draw_grid()

    def update_grid_opacity(self, type, val):
        val = int(val)
        if type == "minor":
            self.minor_opacity = val
        elif type == "major":
            self.major_opacity = val
        self.draw_grid()

    def update_dark_mode(self, is_dark):
        self.dark_mode = is_dark
        if self.dark_mode:
            self.canvas.config(bg="black")
        else:
            self.canvas.config(bg="white")
        self.draw_grid()

    def load_textures(self):
        self.original_textures = {
            "mud": Image.open("Mud.png"),
            "dark_mud": Image.open("Darkmud.png"),
        }
        self.textures = {}
        self.textures["mud"] = ImageTk.PhotoImage(
            self.original_textures["mud"].resize(((552 - 448) * CELL_SIZE, (550 - 446) * CELL_SIZE), Image.Resampling.LANCZOS)
        )
        self.textures["dark_mud"] = ImageTk.PhotoImage(
            self.original_textures["dark_mud"].resize(((510 - 489) * CELL_SIZE, (508 - 486) * CELL_SIZE), Image.Resampling.LANCZOS)
        )

    def blend_color(self, hex_color, opacity):
        if not (hex_color.startswith("#") and len(hex_color) == 7):
            return "#000000"
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        a = opacity / 100.0
        if self.dark_mode:
            nr = int(a * r)
            ng = int(a * g)
            nb = int(a * b)
        else:
            nr = int(a * r + (1 - a) * 255)
            ng = int(a * g + (1 - a) * 255)
            nb = int(a * b + (1 - a) * 255)
        return f"#{nr:02x}{ng:02x}{nb:02x}"

    def on_mouse_move(self, event):
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        x = int((canvas_x - self.pan_x) / adjusted_cell_size)
        y = GRID_SIZE - int((canvas_y - self.pan_y) / adjusted_cell_size) - 1
        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
            self.coord_label.config(text=f"Coordinates: ({x}, {y})")
        else:
            self.coord_label.config(text="Coordinates: Out of Bounds")
        self.update_shadow(event)
        
    def set_start_position(self, x, y):
        self.pan_x = -x * CELL_SIZE * self.zoom_factor + 400
        self.pan_y = -(GRID_SIZE - y - 1) * CELL_SIZE * self.zoom_factor + 400

    def zoom(self, event):
        scale_factor = 1.1 if event.delta > 0 else 0.9
        cursor_x = self.canvas.canvasx(event.x)
        cursor_y = self.canvas.canvasy(event.y)
        rel_x = (cursor_x - self.pan_x) / (CELL_SIZE * self.zoom_factor)
        rel_y = (cursor_y - self.pan_y) / (CELL_SIZE * self.zoom_factor)
        self.zoom_factor *= scale_factor
        self.pan_x = cursor_x - (rel_x * CELL_SIZE * self.zoom_factor)
        self.pan_y = cursor_y - (rel_y * CELL_SIZE * self.zoom_factor)
        self.draw_grid()

    def start_pan(self, event):
        self.is_panning = True
        self.selected_tool = None
        self.status_bar.config(text="Tool: Panning")
        self.start_x = event.x
        self.start_y = event.y

    def pan(self, event):
        if self.is_panning:
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            self.pan_x += dx
            self.pan_y += dy
            self.start_x = event.x
            self.start_y = event.y
            self.draw_grid()

    def stop_pan(self, event):
        self.is_panning = False

    def save_state(self):
        state = {
            "placed_objects": {f"{x},{y}": data for (x, y), data in self.placed_objects.items()},
            "terrain_cells": {f"{x},{y}": terrain for (x, y), terrain in self.terrain_cells.items()},
            "pan_x": self.pan_x,
            "pan_y": self.pan_y,
            "zoom_factor": self.zoom_factor
        }
        with open("autosave.json", "w") as f:
            json.dump(state, f)

    def load_state(self):
        if os.path.exists("autosave.json"):
            with open("autosave.json", "r") as f:
                state = json.load(f)
            self.placed_objects = {}
            for key, data in state.get("placed_objects", {}).items():
                x, y = map(int, key.split(","))
                self.placed_objects[(x, y)] = data
            self.terrain_cells = {}
            for key, terrain in state.get("terrain_cells", {}).items():
                x, y = map(int, key.split(","))
                self.terrain_cells[(x, y)] = terrain
            self.pan_x = state.get("pan_x", self.pan_x)
            self.pan_y = state.get("pan_y", self.pan_y)
            self.zoom_factor = state.get("zoom_factor", self.zoom_factor)

    def autosave(self):
        self.save_state()
        self.root.after(5000, self.autosave)

    def load_weekly_schedule(self):
        """Loads conductor assignments and VS tasks from 'weekly_schedule.json' if it exists."""
        if os.path.exists("weekly_schedule.json"):
            with open("weekly_schedule.json", "r") as f:
                data = json.load(f)
            self.conductor_assignments = data.get("conductor_assignments", {})
            self.vs_tasks_by_weekday = data.get("vs_tasks_by_weekday", {})
        else:
            self.conductor_assignments = {}
            self.vs_tasks_by_weekday = {}

    def update_train_conductor_file(self):
        """Writes the current train conductor assignments to 'train_conductor_list.txt'."""
        with open("train_conductor_list.txt", "w") as f:
            f.write("Train Conductor List:\n")
            for date in sorted(self.conductor_assignments.keys()):
                f.write(f"{date}: {self.conductor_assignments[date]}\n")

    def toggle_delete_mode(self):
        if self.selected_tool and self.selected_tool["type"] == "delete":
            self.selected_tool = None
            self.status_bar.config(text="Tool: None")
        else:
            self.selected_tool = {"type": "delete"}
            self.status_bar.config(text="Tool: Delete Mode")

    def place_element(self, event):
        if not self.selected_tool:
            return
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        x = int((self.canvas.canvasx(event.x) - self.pan_x) / adjusted_cell_size)
        y = GRID_SIZE - int((self.canvas.canvasy(event.y) - self.pan_y) / adjusted_cell_size) - 1
        if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
            return
        if self.selected_tool["type"] == "delete":
            for center, data in list(self.placed_objects.items()):
                obj_size = data.get("size", (3, 3))
                w, h = obj_size
                cx, cy = center
                x_start = cx - w // 2
                y_start = cy - h // 2
                if x_start <= x < x_start + w and y_start <= y < y_start + h:
                    del self.placed_objects[center]
                    self.draw_grid()
                    return
            return
        elif self.selected_tool["type"] == "terrain":
            self.terrain_cells[(x, y)] = self.selected_tool["terrain"]
        elif self.selected_tool["type"] == "object":
            if self.selected_tool.get("unique", False):
                for center, data in list(self.placed_objects.items()):
                    if data.get("tag") == self.selected_tool.get("tag"):
                        del self.placed_objects[center]
                        break
            obj_size = self.selected_tool.get("size", (3, 3))
            w, h = obj_size
            for (obj_x, obj_y), existing_obj in self.placed_objects.items():
                if (abs(obj_x - x) < w and abs(obj_y - y) < h):
                    print("Cannot place object: Space occupied!")
                    return
            self.placed_objects[(x, y)] = {
                "tag": self.selected_tool["tag"],
                "color": self.selected_tool["color"],
                "size": obj_size,
                "avatar": self.selected_tool.get("avatar")
            }
        self.draw_grid()
        self.canvas.delete("shadow")

    def update_alliance_members_submenu(self):
        self.custom_alliance_submenu.delete(0, tk.END)
        rank_list = ["R1", "R2", "R3", "R4", "R5"]
        self.alliance_member_submenus = {}
        for rank in rank_list:
            submenu = tk.Menu(self.custom_alliance_submenu, tearoff=0)
            self.custom_alliance_submenu.add_cascade(label=rank, menu=submenu)
            self.alliance_member_submenus[rank] = submenu
        for member in self.alliance_members:
            rank = member.get("Rank", "R1")
            name = member.get("Name", "Unnamed")
            if member.get("Avatar") and os.path.exists(member["Avatar"]):
                try:
                    avatar_img = Image.open(member["Avatar"])
                    avatar_img = avatar_img.resize((16, 16), Image.Resampling.LANCZOS)
                    avatar_photo = ImageTk.PhotoImage(avatar_img)
                except Exception:
                    avatar_photo = None
            else:
                avatar_photo = None
            if avatar_photo is None:
                default_color = self.alliance_default_colors.get(rank, "#000000")
                from PIL import Image as PILImage
                img = PILImage.new("RGB", (16, 16), default_color)
                avatar_photo = ImageTk.PhotoImage(img)
            submenu = self.alliance_member_submenus.get(rank)
            if submenu:
                submenu.add_command(
                    label=name,
                    image=avatar_photo,
                    compound="left",
                    command=lambda m=member: self.activate_preset_object(
                        m.get("Name", "Unnamed"),
                        m.get("Avatar") if m.get("Avatar") and os.path.exists(m.get("Avatar"))
                            else self.alliance_default_colors.get(m.get("Rank", "R1"), "#000000"),
                        m.get("Size", (3, 3)),
                        unique=True,
                        avatar=m.get("Avatar")
                    )
                )
                if not hasattr(self, "alliance_member_images"):
                    self.alliance_member_images = []
                self.alliance_member_images.append(avatar_photo)

    def draw_grid(self):
        self.canvas.delete("all")
        self.redraw_terrain()
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        for i in range(GRID_SIZE + 1):
            x = i * adjusted_cell_size + self.pan_x
            y = (GRID_SIZE - i) * adjusted_cell_size + self.pan_y
            if i % 9 == 0:
                line_color = self.blend_color(self.major_grid_color, self.major_opacity)
                self.canvas.create_line(x, self.pan_y, x, GRID_SIZE * adjusted_cell_size + self.pan_y, fill=line_color, tags="grid")
                self.canvas.create_line(self.pan_x, y, GRID_SIZE * adjusted_cell_size + self.pan_x, y, fill=line_color, tags="grid")
            else:
                if adjusted_cell_size >= self.grid_zoom_threshold:
                    line_color = self.blend_color(self.minor_grid_color, self.minor_opacity)
                    self.canvas.create_line(x, self.pan_y, x, GRID_SIZE * adjusted_cell_size + self.pan_y, fill=line_color, tags="grid")
                    self.canvas.create_line(self.pan_x, y, GRID_SIZE * adjusted_cell_size + self.pan_x, y, fill=line_color, tags="grid")
        self.redraw_objects()

    def redraw_terrain(self):
        self.canvas.delete("terrain")
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        mud_width = (552 - 448) * adjusted_cell_size
        mud_height = (550 - 446) * adjusted_cell_size
        dark_mud_width = (510 - 489) * adjusted_cell_size
        dark_mud_height = (508 - 486) * adjusted_cell_size
        mud_texture = self.original_textures["mud"].resize((int(mud_width), int(mud_height)), Image.Resampling.LANCZOS)
        dark_mud_texture = self.original_textures["dark_mud"].resize((int(dark_mud_width), int(dark_mud_height)), Image.Resampling.LANCZOS)
        self.textures["mud"] = ImageTk.PhotoImage(mud_texture)
        self.textures["dark_mud"] = ImageTk.PhotoImage(dark_mud_texture)
        mud_x = 448 * adjusted_cell_size + self.pan_x
        mud_y = (GRID_SIZE - 550) * adjusted_cell_size + self.pan_y
        dark_mud_x = 489 * adjusted_cell_size + self.pan_x
        dark_mud_y = (GRID_SIZE - 508) * adjusted_cell_size + self.pan_y
        self.canvas.create_image(mud_x, mud_y, image=self.textures["mud"], anchor="nw", tags="terrain")
        self.canvas.create_image(dark_mud_x, dark_mud_y, image=self.textures["dark_mud"], anchor="nw", tags="terrain")



    def update_shadow(self, event):
        if self.selected_tool is None or "type" not in self.selected_tool:
            self.canvas.delete("shadow")
            return
        if self.selected_tool["type"] != "object":
            self.canvas.delete("shadow")
            return
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        x = int((self.canvas.canvasx(event.x) - self.pan_x) / adjusted_cell_size)
        y = GRID_SIZE - int((self.canvas.canvasy(event.y) - self.pan_y) / adjusted_cell_size) - 1
        if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
            self.canvas.delete("shadow")
            return
        obj_size = self.selected_tool.get("size", (3, 3))
        w, h = obj_size
        x_start = x - w // 2
        y_start = y - h // 2
        x_pos = x_start * adjusted_cell_size + self.pan_x
        y_pos = (GRID_SIZE - (y_start + h)) * adjusted_cell_size + self.pan_y
        self.canvas.delete("shadow")
        self.canvas.create_rectangle(
            x_pos, y_pos, x_pos + w * adjusted_cell_size, y_pos + h * adjusted_cell_size,
            fill=self.selected_tool["color"], outline="black", stipple="gray50", tags="shadow"
        )
        self.canvas.create_text(
            x_pos + (w * adjusted_cell_size) / 2, y_pos + (h * adjusted_cell_size) / 2,
            text=self.selected_tool["tag"], fill="black", font=("Arial", int(adjusted_cell_size / 3)), tags="shadow"
        )

    def add_custom_object(self):
        tag = simpledialog.askstring("Custom Object", "Enter object tag:")
        if not tag:
            return
        color = colorchooser.askcolor(title="Choose Object Color")[1]
        if not color:
            return
        size_str = simpledialog.askstring("Custom Object Size", "Enter size (width,height) in cells, e.g. 3,3:", initialvalue="3,3")
        try:
            w, h = map(int, size_str.split(","))
        except:
            w, h = 3, 3
        self.custom_objects[tag] = {"color": color, "size": (w, h)}
        self.update_custom_submenu()

    def update_custom_submenu(self):
        self.custom_submenu.delete(0, "end")
        self.custom_submenu.add_command(label="Add Custom Object", command=self.add_custom_object)
        for tag, data in self.custom_objects.items():
            self.custom_submenu.add_command(
                label=tag,
                command=lambda t=tag, d=data: self.activate_preset_object(t, d["color"], d["size"])
            )

    def edit_object_text(self, event):
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        x = int((self.canvas.canvasx(event.x) - self.pan_x) / adjusted_cell_size)
        y = GRID_SIZE - int((self.canvas.canvasy(event.y) - self.pan_y) / adjusted_cell_size) - 1
        if (x, y) in self.placed_objects:
            current_text = self.placed_objects[(x, y)]["tag"]
            new_text = simpledialog.askstring("Edit Object", "Enter new text:", initialvalue=current_text)
            if new_text is not None:
                self.placed_objects[(x, y)]["tag"] = new_text
                self.draw_grid()

    def deselect_tool(self, event=None):
        self.selected_tool = None
        self.status_bar.config(text="Tool: None")

    # ------------------------------
    # Schedule Management
    # ------------------------------
    def manage_weekly_schedule(self):
        schedule_win = tk.Toplevel(self.root)
        schedule_win.title("Weekly Schedule")
        schedule_win.geometry("800x600")
        
        # Create a Notebook with a tab for each week.
        self.schedule_notebook = ttk.Notebook(schedule_win)
        self.schedule_notebook.pack(fill=tk.BOTH, expand=True)
        
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        # For example, show previous 2 weeks, current week, and next week.
        week_dates = [monday - datetime.timedelta(weeks=i) for i in range(2, 0, -1)] + [monday] + [monday + datetime.timedelta(weeks=i) for i in range(1, 2)]
        
        self.schedule_listboxes = {}  # keyed by week (ISO string), each value is a dict: day_name -> listbox
        
        for week_monday in week_dates:
            week_key = week_monday.isoformat()
            tab_label = f"Week of {week_key}"
            frame = tk.Frame(self.schedule_notebook)
            self.schedule_notebook.add(frame, text=tab_label)
            
            day_frames = {}
            for i in range(7):
                day_date = week_monday + datetime.timedelta(days=i)
                day_name = day_date.strftime("%A")
                subframe = tk.Frame(frame, relief=tk.RIDGE, borderwidth=1)
                subframe.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
                tk.Label(subframe, text=f"{day_name}\n{day_date.isoformat()}").pack()
                lb = tk.Listbox(subframe, height=4)
                lb.bind("<Button-3>", self.on_schedule_item_right_click)
                lb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
                # Store the day date with the listbox for later reference.
                lb.day_date = day_date.isoformat()
                # Pre-populate with two fixed items:
                conductor = self.conductor_assignments.get(lb.day_date, "Not Assigned")
                weekday = datetime.date.fromisoformat(lb.day_date).strftime("%A")
                vs_tasks = self.vs_tasks_by_weekday.get(weekday, [])

                lb.insert(tk.END, f"Conductor: {conductor}")
                lb.insert(tk.END, "VS:")  # VS header on its own row
                if vs_tasks:
                    for task in vs_tasks:
                        lb.insert(tk.END, task)
                else:
                    lb.insert(tk.END, "VS: No tasks")
                # Bind double-click event on each listbox.
                lb.bind("<Double-Button-1>", self.on_schedule_item_double_click)
                day_frames[day_name] = lb
            self.schedule_listboxes[week_key] = day_frames
        
        tk.Button(schedule_win, text="Save Schedule", command=self.save_weekly_schedule).pack(pady=5)

    def on_schedule_item_right_click(self, event):
        lb = event.widget
        index = lb.nearest(event.y)
        # Only allow deletion for task items (indices >= 2)
        if index < 2:
            return
        menu = tk.Menu(lb, tearoff=0)
        menu.add_command(label="Delete Task", command=lambda: self.delete_schedule_task(lb, index))
        menu.tk_popup(event.x_root, event.y_root)

    def delete_schedule_task(self, lb, index):
        day_date = lb.day_date  # e.g. "2025-03-21"
        task_text = lb.get(index)
        weekday = datetime.date.fromisoformat(day_date).strftime("%A")
        
        # Check if the task is recurring and/or single
        recurring_tasks = self.vs_tasks_by_weekday.get(weekday, [])
        single_tasks = self.vs_tasks.get(day_date, [])
        is_recurring = task_text in recurring_tasks
        is_single = task_text in single_tasks

        if is_recurring:
            # Ask if the user wants to remove the task from all days or just this instance.
            response = messagebox.askyesnocancel(
                "Delete Recurring Task",
                f"Task '{task_text}' is recurring.\n\n"
                "Yes: Delete from all {weekday}s\nNo: Delete only for this day\nCancel: Abort deletion"
            )
            if response is None:
                return  # Cancelled
            elif response:  # Yes: Delete from all days
                recurring_tasks.remove(task_text)
                self.vs_tasks_by_weekday[weekday] = recurring_tasks
            else:  # No: Delete only for this day by adding an exception
                exceptions = self.vs_task_exceptions.get(day_date, [])
                if task_text not in exceptions:
                    exceptions.append(task_text)
                    self.vs_task_exceptions[day_date] = exceptions
        elif is_single:
            # Delete from single tasks for that day
            single_tasks.remove(task_text)
            self.vs_tasks[day_date] = single_tasks
        else:
            # Task not found in either; do nothing or simply remove from display.
            pass

        self.save_weekly_schedule()
        self.update_schedule_display()

    def update_schedule_display(self):
        """Updates each schedule listbox to show the combined VS tasks for its date.
        Recurring tasks (by weekday) are combined with any single tasks (by date)."""
        for week_key, day_boxes in self.schedule_listboxes.items():
            for day_name, lbox in day_boxes.items():
                day_date = lbox.day_date  # e.g., "2025-03-21"
                weekday = datetime.date.fromisoformat(day_date).strftime("%A")
                recurring_tasks = self.vs_tasks_by_weekday.get(weekday, [])
                single_tasks = self.vs_tasks.get(day_date, [])
                combined_tasks = recurring_tasks + single_tasks
                
                # Assume index 0 is the Conductor line and index 1 is the VS header.
                # Remove any items after index 1 and reinsert the VS header and tasks.
                current_items = lbox.get(0, tk.END)
                if len(current_items) > 1:
                    lbox.delete(1, tk.END)
                lbox.insert(tk.END, "VS:")
                if combined_tasks:
                    for task in combined_tasks:
                        lbox.insert(tk.END, task)
                else:
                    lbox.insert(tk.END, "VS: No tasks")

    def add_single_task(self):
        """Opens a dialog to add a single VS task to a specific date."""
        win = tk.Toplevel(self.root)
        win.title("Add Single VS Task")
        
        tk.Label(win, text="Enter Date (YYYY-MM-DD):").pack(padx=10, pady=5)
        date_entry = tk.Entry(win, width=20)
        date_entry.pack(padx=10, pady=5)
        
        tk.Label(win, text="Task Description:").pack(padx=10, pady=5)
        task_entry = tk.Entry(win, width=50)
        task_entry.pack(padx=10, pady=5)
        
        def save_single():
            date_str = date_entry.get().strip()
            task = task_entry.get().strip()
            try:
                datetime.date.fromisoformat(date_str)
            except Exception:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return
            if not task:
                messagebox.showerror("Error", "Task description cannot be empty.")
                return
            # Use self.vs_tasks (keyed by date) for single tasks
            if date_str in self.vs_tasks:
                if task not in self.vs_tasks[date_str]:
                    self.vs_tasks[date_str].append(task)
            else:
                self.vs_tasks[date_str] = [task]
            self.save_weekly_schedule()
            self.update_schedule_display()
            win.destroy()
        
        tk.Button(win, text="Save Single Task", command=save_single).pack(pady=10)


    def create_recurring_task(self):
        """Opens a dialog to create a new recurring VS task.
        The user can enter a task description and select one or more weekdays for the task to apply."""
        win = tk.Toplevel(self.root)
        win.title("Create Recurring VS Task")
        
        tk.Label(win, text="Task Description:").pack(padx=10, pady=5)
        task_entry = tk.Entry(win, width=50)
        task_entry.pack(padx=10, pady=5)
        
        tk.Label(win, text="Select Weekdays:").pack(padx=10, pady=5)
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday_vars = {}
        for day in weekdays:
            var = tk.BooleanVar(value=False)
            weekday_vars[day] = var
            tk.Checkbutton(win, text=day, variable=var).pack(anchor="w", padx=20)
        
        def save_recurring():
            task = task_entry.get().strip()
            if not task:
                messagebox.showerror("Error", "Task description cannot be empty.")
                return
            for day in weekdays:
                if weekday_vars[day].get():
                    if day in self.vs_tasks_by_weekday:
                        if task not in self.vs_tasks_by_weekday[day]:
                            self.vs_tasks_by_weekday[day].append(task)
                    else:
                        self.vs_tasks_by_weekday[day] = [task]
            self.save_weekly_schedule()  # Save changes to file
            self.update_schedule_display()  # Refresh displayed tasks
            win.destroy()
        
        tk.Button(win, text="Save Recurring Task", command=save_recurring).pack(pady=10)


    def save_weekly_schedule(self):
        data = {
            "conductor_assignments": self.conductor_assignments,
            "vs_tasks_by_weekday": self.vs_tasks_by_weekday  # Use vs_tasks_by_weekday (not vs_tasks) if saving per weekday
        }
        with open("weekly_schedule.json", "w") as f:
            json.dump(data, f, indent=4)
        messagebox.showinfo("Weekly Schedule", "Schedule saved successfully.")

    def on_schedule_item_double_click(self, event):
        lb = event.widget
        selection = lb.curselection()
        if not selection:
            return
        idx = selection[0]
        # Index 0: Conductor event; Index 1: VS event.
        if idx == 0:
            self.open_conductor_assignment_dialog(lb)
        elif idx == 1:
            self.open_vs_edit_dialog(lb)

    def open_predefined_vs_tasks_dialog(self, vs_listbox):
        win = tk.Toplevel(self.root)
        win.title("Select Predefined VS Tasks")
        task_vars = {}
        # Create a checkbutton for each predefined task
        for task in self.predefined_vs_tasks:
            var = tk.BooleanVar(value=(task in vs_listbox.get(0, tk.END)))
            task_vars[task] = var
            tk.Checkbutton(win, text=task, variable=var).pack(anchor="w")
        def apply_tasks():
            selected_tasks = [task for task, var in task_vars.items() if var.get()]
            vs_listbox.delete(0, tk.END)
            for task in selected_tasks:
                vs_listbox.insert(tk.END, task)
            win.destroy()
        tk.Button(win, text="Apply", command=apply_tasks).pack(pady=5)

    def manage_predefined_vs_tasks(self):
        """Opens a dialog to add, edit, and remove predefined VS tasks."""
        win = tk.Toplevel(self.root)
        win.title("Manage Predefined VS Tasks")
        
        listbox = tk.Listbox(win)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Populate the listbox with current predefined tasks
        for task in self.predefined_vs_tasks:
            listbox.insert(tk.END, task)
        
        def refresh_listbox():
            listbox.delete(0, tk.END)
            for task in self.predefined_vs_tasks:
                listbox.insert(tk.END, task)
        
        def add_task():
            new_task = simpledialog.askstring("Add Task", "Enter new VS Task:")
            if new_task:
                self.predefined_vs_tasks.append(new_task)
                refresh_listbox()
        
        def edit_task():
            sel = listbox.curselection()
            if sel:
                index = sel[0]
                current_task = self.predefined_vs_tasks[index]
                new_task = simpledialog.askstring("Edit Task", "Edit VS Task:", initialvalue=current_task)
                if new_task:
                    self.predefined_vs_tasks[index] = new_task
                    refresh_listbox()
        
        def remove_task():
            sel = listbox.curselection()
            if sel:
                index = sel[0]
                if messagebox.askyesno("Confirm Removal", "Are you sure you want to remove this task?"):
                    del self.predefined_vs_tasks[index]
                    refresh_listbox()
        
        button_frame = tk.Frame(win)
        button_frame.pack(pady=5)
        tk.Button(button_frame, text="Add Task", command=add_task).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Edit Task", command=edit_task).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Remove Task", command=remove_task).pack(side=tk.LEFT, padx=5)


    def initialize_preset_terrain(self):
        """Sets up preset mud terrain areas (PvP & restricted zones) by coloring the original grid cells."""
        # PvP Mud Area
        for x in range(448, 552):  # x: 448-551
            for y in range(446, 550):  # y: 446-549
                self.terrain_cells[(x, y)] = "mud"

        # Dark Mud (Restricted Placement Area)
        for x in range(489, 510):  # x: 489-509
            for y in range(486, 508):  # y: 486-507
                self.terrain_cells[(x, y)] = "dark_mud"

        # Force terrain to be drawn after grid
        self.redraw_terrain()

    def redraw_objects(self):
        """Redraws all objects on top of the grid and terrain."""
        self.canvas.delete("object")
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        for (x, y), data in self.placed_objects.items():
            obj_size = data.get("size", (3,3))
            w, h = obj_size
            x_start = x - w // 2
            y_start = y - h // 2
            x_pos = x_start * adjusted_cell_size + self.pan_x
            y_pos = (GRID_SIZE - (y_start + h)) * adjusted_cell_size + self.pan_y
            if data.get("avatar") and os.path.exists(data["avatar"]):
                try:
                    img = Image.open(data["avatar"])
                    # Resize the image to fit the object's cell area
                    img = img.resize((int(w * adjusted_cell_size), int(h * adjusted_cell_size)), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self.canvas.create_image(x_pos, y_pos, image=photo, anchor="nw", tags="object")
                    # Save reference to avoid garbage collection
                    if not hasattr(self, "object_images"):
                        self.object_images = []
                    self.object_images.append(photo)
                except Exception as e:
                    print("Error loading avatar image:", e)
                    # Fallback to drawing rectangle
                    self.canvas.create_rectangle(
                        x_pos, y_pos, x_pos + w * adjusted_cell_size, y_pos + h * adjusted_cell_size,
                        fill=data["color"], outline="black", tags="object"
                    )
                    self.canvas.create_text(
                        x_pos + (w * adjusted_cell_size) / 2, y_pos + (h * adjusted_cell_size) / 2,
                        text=data["tag"], fill="white", font=("Arial", int(adjusted_cell_size / 3)), tags="object"
                    )
            else:
                self.canvas.create_rectangle(
                    x_pos, y_pos, x_pos + w * adjusted_cell_size, y_pos + h * adjusted_cell_size,
                    fill=data["color"], outline="black", tags="object"
                )
                self.canvas.create_text(
                    x_pos + (w * adjusted_cell_size) / 2, y_pos + (h * adjusted_cell_size) / 2,
                    text=data["tag"], fill="white", font=("Arial", int(adjusted_cell_size / 3)), tags="object"
                )


    def handle_right_click(self, event):
            """If right-click is on a placed object, open context menu; otherwise, deselect tool."""
            adjusted_cell_size = CELL_SIZE * self.zoom_factor
            x = int((self.canvas.canvasx(event.x) - self.pan_x) / adjusted_cell_size)
            y = GRID_SIZE - int((self.canvas.canvasy(event.y) - self.pan_y) / adjusted_cell_size) - 1

            found_obj = None
            for center, data in self.placed_objects.items():
                obj_size = data.get("size", (3, 3))
                w, h = obj_size
                cx, cy = center
                x_start = cx - w // 2
                y_start = cy - h // 2
                if x_start <= x < x_start + w and y_start <= y < y_start + h:
                    found_obj = center
                    break

            if found_obj is not None:
                self.show_object_context_menu(event, found_obj)
            else:
                self.deselect_tool(event)

    def open_conductor_assignment_dialog(self, lb):
        day_date = lb.day_date
        win = tk.Toplevel(self.root)
        win.title(f"Assign Conductor for {day_date}")
        # Create checkbuttons for each rank.
        ranks = ["R1", "R2", "R3", "R4", "R5"]
        rank_vars = {rank: tk.BooleanVar(value=True) for rank in ranks}
        row = 0
        tk.Label(win, text="Filter by Rank:").grid(row=row, column=0, columnspan=2)
        row += 1
        for rank in ranks:
            tk.Checkbutton(win, text=rank, variable=rank_vars[rank]).grid(row=row, column=0, sticky="w")
            row += 1
        
        tk.Label(win, text="Alliance Members:").grid(row=0, column=2)
        member_listbox = tk.Listbox(win, selectmode=tk.SINGLE)
        member_listbox.grid(row=1, column=2, rowspan=5, padx=10, pady=5)
        
        def update_member_list():
            member_listbox.delete(0, tk.END)
            for member in self.alliance_members:
                member_rank = member.get("Rank", "R1")
                if rank_vars[member_rank].get():
                    member_listbox.insert(tk.END, member.get("Name", "Unnamed"))
        
        tk.Button(win, text="Filter", command=update_member_list).grid(row=row, column=0, columnspan=3, pady=5)
        update_member_list()  # Initial population
        
        def assign_member():
            sel = member_listbox.curselection()
            if sel:
                member_name = member_listbox.get(sel[0])
                self.conductor_assignments[day_date] = member_name
                lb.delete(0)
                lb.insert(0, f"Conductor: {member_name}")
                self.update_train_conductor_file()
                win.destroy()
        tk.Button(win, text="Assign", command=assign_member).grid(row=row+1, column=0, columnspan=3, pady=5)

    def open_vs_edit_dialog(self, lb):
        day_date = lb.day_date
        win = tk.Toplevel(self.root)
        win.title(f"Edit VS Event for {day_date}")
        tk.Label(win, text="VS Tasks:").pack(padx=10, pady=5)
        vs_listbox = tk.Listbox(win, selectmode=tk.SINGLE)
        vs_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        current_tasks = self.vs_tasks.get(day_date, [])
        tk.Button(win, text="Select Predefined Tasks", command=lambda: self.open_predefined_vs_tasks_dialog(vs_listbox)).pack(padx=10, pady=5)
        for task in current_tasks:
            vs_listbox.insert(tk.END, task)
        def add_task():
            task = simpledialog.askstring("Add VS Task", "Enter VS Task:")
            if task:
                vs_listbox.insert(tk.END, task)
        def remove_task():
            sel = vs_listbox.curselection()
            if sel:
                vs_listbox.delete(sel[0])
        def save_tasks():
            tasks = list(vs_listbox.get(0, tk.END))
            # Get the weekday from the current day_date
            weekday = datetime.date.fromisoformat(lb.day_date).strftime("%A")
            self.vs_tasks_by_weekday[weekday] = tasks
            # Now update every listbox whose day has the same weekday:
            for week_key, day_boxes in self.schedule_listboxes.items():
                for day_name, lbox in day_boxes.items():
                    # Determine the weekday for each listbox:
                    current_weekday = datetime.date.fromisoformat(lbox.day_date).strftime("%A")
                    if current_weekday == weekday:
                        lbox.delete(1, tk.END)  # Remove all items after the Conductor entry
                        lbox.insert(tk.END, "VS:")
                        if tasks:
                            for task in tasks:
                                lbox.insert(tk.END, task)
                        else:
                            lbox.insert(tk.END, "VS: No tasks")
            win.destroy()
        tk.Button(win, text="Add Task", command=add_task).pack(padx=10, pady=5)
        tk.Button(win, text="Remove Task", command=remove_task).pack(padx=10, pady=5)
        tk.Button(win, text="Save", command=save_tasks).pack(padx=10, pady=5)

    # ------------------------------
    # Alliance Management (unchanged)
    # ------------------------------
    def manage_alliance_members(self):
        self.alliance_win = tk.Toplevel(self.root)
        self.alliance_win.title("Alliance Members")
        self.alliance_win.geometry("400x300")
        self.alliance_members_changed = False
        self.alliance_win.protocol("WM_DELETE_WINDOW", self.close_alliance_win)
        self.member_listbox = tk.Listbox(self.alliance_win)
        self.member_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_member_listbox()
        btn_frame = tk.Frame(self.alliance_win)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Add Member", command=self.add_alliance_member).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Edit Member", command=self.edit_alliance_member).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Remove Member", command=self.remove_alliance_member).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Save Changes", command=self.save_alliance_members).pack(side=tk.LEFT, padx=5)

    def update_member_listbox(self):
        self.member_listbox.delete(0, tk.END)
        for member in self.alliance_members:
            display = f"{member.get('Name', 'Unnamed')} - {member.get('Rank', 'N/A')}"
            self.member_listbox.insert(tk.END, display)

    def add_alliance_member(self):
        add_win = tk.Toplevel(self.root)
        add_win.title("Add Alliance Member")
        tk.Label(add_win, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        name_var = tk.StringVar()
        tk.Entry(add_win, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(add_win, text="Rank:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        rank_var = tk.StringVar(value="R1")
        ranks = ["R1", "R2", "R3", "R4", "R5"]
        tk.OptionMenu(add_win, rank_var, *ranks).grid(row=1, column=1, padx=5, pady=5)
        tk.Label(add_win, text="Avatar:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        avatar_var = tk.StringVar(value="")
        def choose_avatar():
            file_path = filedialog.askopenfilename(initialdir="Images/avatars", title="Select Avatar Image",
                                                   filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif")])
            if file_path:
                avatar_var.set(file_path)
        tk.Button(add_win, text="Choose Avatar", command=choose_avatar).grid(row=2, column=1, padx=5, pady=5)
        def on_add():
            name = name_var.get().strip()
            if not name:
                tk.messagebox.showerror("Error", "Name cannot be empty.")
                return
            new_member = {
                "Name": name,
                "Rank": rank_var.get(),
                "Avatar": avatar_var.get() if avatar_var.get() else self.alliance_default_colors.get(rank_var.get(), "#000000")
            }
            self.alliance_members.append(new_member)
            self.alliance_members_changed = True
            self.update_member_listbox()
            add_win.destroy()
        tk.Button(add_win, text="Add Member", command=on_add).grid(row=3, column=0, columnspan=2, pady=10)

    def edit_alliance_member(self):
        if not self.alliance_members:
            tk.messagebox.showerror("Error", "No members available to edit.")
            return
        idxs = self.member_listbox.curselection()
        if not idxs:
            tk.messagebox.showerror("Error", "No member selected.")
            return
        idx = idxs[0]
        member = self.alliance_members[idx]
        edit_win = tk.Toplevel(self.root)
        edit_win.title("Edit Alliance Member")
        tk.Label(edit_win, text="Name:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        name_var = tk.StringVar(value=member.get("Name", ""))
        tk.Entry(edit_win, textvariable=name_var).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(edit_win, text="Rank:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        rank_var = tk.StringVar(value=member.get("Rank", "R1"))
        ranks = ["R1", "R2", "R3", "R4", "R5"]
        tk.OptionMenu(edit_win, rank_var, *ranks).grid(row=1, column=1, padx=5, pady=5)
        tk.Label(edit_win, text="Avatar:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        avatar_var = tk.StringVar(value=member.get("Avatar", ""))
        def choose_avatar():
            file_path = filedialog.askopenfilename(initialdir="Images/avatars", title="Select Avatar Image",
                                                   filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif")])
            if file_path:
                avatar_var.set(file_path)
        tk.Button(edit_win, text="Choose Avatar", command=choose_avatar).grid(row=2, column=1, padx=5, pady=5)
        def on_edit():
            new_name = name_var.get().strip()
            if not new_name:
                tk.messagebox.showerror("Error", "Name cannot be empty.")
                return
            member["Name"] = new_name
            member["Rank"] = rank_var.get()
            member["Avatar"] = avatar_var.get() if avatar_var.get() else self.alliance_default_colors.get(rank_var.get(), "#000000")
            self.alliance_members[idx] = member
            self.alliance_members_changed = True
            self.update_member_listbox()
            edit_win.destroy()
        tk.Button(edit_win, text="Save Changes", command=on_edit).grid(row=3, column=0, columnspan=2, pady=10)

    def remove_alliance_member(self):
        if not self.alliance_members:
            tk.messagebox.showerror("Error", "No members available to remove.")
            return
        idxs = self.member_listbox.curselection()
        if not idxs:
            tk.messagebox.showerror("Error", "No member selected.")
            return
        idx = idxs[0]
        del self.alliance_members[idx]
        self.alliance_members_changed = True
        self.update_member_listbox()

    def close_alliance_win(self):
        if self.alliance_members_changed:
            response = tk.messagebox.askyesnocancel("Save Changes?", "You have unsaved changes. Save them before closing?")
            if response is None:
                return
            elif response:
                self.save_alliance_members()
        self.alliance_win.destroy()

    def save_alliance_members(self):
        with open("alliance_members.txt", "w") as f:
            json.dump(self.alliance_members, f, indent=4)
        self.alliance_members_changed = False
        tk.messagebox.showinfo("Save Alliance Members", "Alliance members saved successfully.")

    def create_ui(self):
        self.canvas = tk.Canvas(self.root, bg="white", width=800, height=800)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)
        place_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Place Object", menu=place_menu)
        self.create_object_submenu(place_menu, "Alliance", {
            "R1": "#2C3E50", "R2": "#34495E", "R3": "#5D6D7E", "R4": "#2874A6", "R5": "#1F618D"
        })
        self.create_object_submenu(place_menu, "Friendly", {
            "1": "#145A32", "2": "#1E8449", "3": "#28B463", "4": "#52BE80", "5": "#82E0AA"
        })
        self.create_object_submenu(place_menu, "Enemy", {
            "1": "#922B21", "2": "#A93226", "3": "#C0392B", "4": "#E74C3C", "5": "#F1948A"
        })
        self.create_object_submenu(place_menu, "Other", {
            "MG": "#FF5733"
        })
        self.custom_objects = {}
        self.custom_submenu = tk.Menu(place_menu, tearoff=0)
        place_menu.add_cascade(label="Custom", menu=self.custom_submenu)
        self.custom_submenu.add_command(label="Add Custom Object", command=self.add_custom_object)
        self.update_custom_submenu()
        self.custom_alliance_submenu = tk.Menu(place_menu, tearoff=0)
        place_menu.add_cascade(label="Alliance Members", menu=self.custom_alliance_submenu)
        self.update_alliance_members_submenu()
        settings_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Grid Properties", command=self.edit_grid_properties)
        delete_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="🗑 Delete Mode", menu=delete_menu)
        delete_menu.add_command(label="Toggle Delete", command=self.toggle_delete_mode)
        self.coord_label = tk.Label(self.root, text="Coordinates: (0,0)", font=("Arial", 12))
        self.coord_label.pack()
        self.status_bar = tk.Label(self.root, text="Tool: None", bd=1, relief=tk.SUNKEN, anchor="w")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.bind("<Motion>", self.update_coordinates)
        self.canvas.bind("<MouseWheel>", self.zoom)
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.pan)
        self.canvas.bind("<ButtonRelease-2>", self.stop_pan)
        self.canvas.bind("<Button-1>", self.place_element)
        self.canvas.bind("<Button-3>", self.deselect_tool)
        self.canvas.bind("<Double-1>", self.edit_object_text)
        self.canvas.bind("<Button-3>", self.handle_right_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)
        alliance_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Alliance Management", menu=alliance_menu)
        alliance_menu.add_command(label="Manage Members", command=self.manage_alliance_members)
        alliance_menu.add_command(label="Weekly Schedule", command=self.manage_weekly_schedule)
        tk.Button(self.root, text="Manage Predefined Tasks", command=self.manage_predefined_vs_tasks).pack(padx=10, pady=5)

        alliance_menu.add_command(label="Create Recurring Task", command=self.create_recurring_task)
        alliance_menu.add_command(label="Add Single Task", command=self.add_single_task)

        vs_menu = tk.Menu(alliance_menu, tearoff=0)
        alliance_menu.add_cascade(label="Manage VS Tasks", menu=vs_menu)
        vs_menu.add_command(label="Edit Predefined Tasks", command=self.manage_predefined_vs_tasks)
        watermark = tk.Label(self.root, text="Powered by: MaztaPazta", font=("Arial", 10), fg="gray")
        watermark.place(relx=1.0, rely=1.0, anchor="se", x=-5, y=-5)

    def deselect_tool(self, event=None):
        self.selected_tool = None
        self.status_bar.config(text="Tool: None")

    def create_object_submenu(self, parent_menu, label, items):
        submenu = tk.Menu(parent_menu, tearoff=0)
        parent_menu.add_cascade(label=label, menu=submenu)
        for name, color in items.items():
            submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))

    def set_window_title(self, window, base_title):
        window.title(f"{base_title}   Powered by: MaztaPazta")

    def activate_preset_object(self, tag, color, size=(3,3), unique=False, avatar=None):
        self.selected_tool = {
            "type": "object",
            "tag": tag,
            "color": color,
            "size": size,
            "unique": unique,
            "avatar": avatar
        }
        self.status_bar.config(text=f"Tool: Object ({tag})")

    def activate_terrain(self, terrain_type):
        self.selected_tool = {"type": "terrain", "terrain": terrain_type}
        self.status_bar.config(text=f"Tool: Terrain ({terrain_type})")

    def update_coordinates(self, event):
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        x = int((canvas_x - self.pan_x) / adjusted_cell_size)
        y = GRID_SIZE - int((canvas_y - self.pan_y) / adjusted_cell_size) - 1
        if 0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE:
            self.coord_label.config(text=f"Coordinates: ({x}, {y})")
        else:
            self.coord_label.config(text="Coordinates: Out of Bounds")

# Run the Application
root = tk.Tk()
app = GridApp(root)
root.mainloop()
