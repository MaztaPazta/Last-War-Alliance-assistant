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

        self.friendly_objects = {"1": "#145A32", "2": "#1E8449", "3": "#28B463", "4": "#52BE80", "5": "#82E0AA"}
        self.enemy_objects    = {"1": "#922B21", "2": "#A93226", "3": "#C0392B", "4": "#E74C3C", "5": "#F1948A"}
        self.other_objects    = {"MG": "#FF5733"}

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

        # For multi-selection and moving:
        self.selected_objects = set()          # Stores keys (e.g., (x,y)) of selected objects
        self.selected_markers = set()          # NEW: For marker selection
        self.marker_dragging = False           # NEW: To track if a marker is being dragged
        self.selection_rect = None             # Canvas item id for the rubberband rectangle
        self.selection_start = None            # Starting point for rectangle selection (canvas coords)
        self.moving_start = None               # Starting point for moving (canvas coords)
        self.original_positions = {}           # Dictionary mapping object keys to their original (x,y) positions when moving
        self.selected_tool = None
        self.original_positions = {}  # Dictionary mapping object keys to their original positions when moving
        
        # For markers (a dictionary keyed by a unique marker ID, e.g. the marker's name)
        self.markers = {}  # Each marker is a dict with keys: "name", "x1", "y1", "x2", "y2", "color"

        # For marker moving/resizing:
        self.current_marker_id = None   # The marker (its key) currently being moved/resized
        self.marker_move_start = None   # The canvas coordinate where the marker drag started
        self.marker_resizing = False    # Flag: True if the user is resizing (dragging a corner)
        self.current_tool = None  # Normal, or "marker_draw" when drawing a marker
        self.marker_draw_start = None  # Canvas (pixel) coordinate where marker drawing starts
        self.marker_draw_rect = None   # The canvas item id for the temporary rectangle
        self.marker_snap_dot_id = None  # canvas item for the little "snap" dot

        # Load textures for terrain
        self.load_textures()

        self.start_coordinate = start_coordinate
        self.set_start_position(*self.start_coordinate)

        # Create UI elements
        self.create_ui()
    
        # Marker-drawing bindings
        self.canvas.bind("<ButtonPress-1>", self.marker_draw_press, add="+")
        self.canvas.bind("<B1-Motion>", self.marker_draw_motion, add="+")
        self.canvas.bind("<ButtonRelease-1>", self.marker_draw_release, add="+")

        # Then bind the general handlers once.
        self.canvas.bind("<ButtonPress-1>", self.on_left_button_press)
        self.canvas.bind("<B1-Motion>", self.on_left_button_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_button_release)


        self.root.bind("<Delete>", self.delete_selected_objects)

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
        if self.current_tool == "marker_draw":
            # Convert the cursor's canvas position → nearest grid corner
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)
            adjusted = CELL_SIZE * self.zoom_factor

            # 1) Convert canvas → grid corner, rounding to nearest integer
            grid_x = round((canvas_x - self.pan_x) / adjusted)
            grid_y = round(GRID_SIZE - (canvas_y - self.pan_y) / adjusted - 1)

            # 2) Convert that grid corner back → canvas coords
            dot_cx = grid_x * adjusted + self.pan_x
            dot_cy = (GRID_SIZE - grid_y) * adjusted + self.pan_y

            # If the dot doesn't exist yet, create it:
            if self.marker_snap_dot_id is None:
                r = 4  # radius of the dot in pixels
                self.marker_snap_dot_id = self.canvas.create_oval(
                    dot_cx - r, dot_cy - r,
                    dot_cx + r, dot_cy + r,
                    fill="red", outline=""
                )
            else:
                # Otherwise, just move the existing dot
                r = 4
                self.canvas.coords(
                    self.marker_snap_dot_id,
                    dot_cx - r, dot_cy - r,
                    dot_cx + r, dot_cy + r
                )
        else:
            # If we’re NOT in marker-draw mode, remove the dot if it exists
            if self.marker_snap_dot_id is not None:
                self.canvas.delete(self.marker_snap_dot_id)
                self.marker_snap_dot_id = None
            
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
            "markers": self.markers,  # <-- added markers
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
            self.markers = state.get("markers", {})  # <-- load markers
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
            # If this is a unique object (for alliance members, for example), remove any previous instance.
            if self.selected_tool.get("unique", False):
                for center, data in list(self.placed_objects.items()):
                    # Compare tags—ensure the tag is set uniquely for alliance member objects.
                    if data.get("tag") == self.selected_tool.get("tag"):
                        del self.placed_objects[center]
                        break

            obj_size = self.selected_tool.get("size", (3, 3))
            w, h = obj_size
            # Check for collision with any other object.
            for (obj_x, obj_y), existing_obj in self.placed_objects.items():
                if abs(obj_x - x) < w and abs(obj_y - y) < h:
                    print("Cannot place object: Space occupied!")
                    return

            # Place the object at the clicked cell.
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
                        self.alliance_default_colors.get(m.get("Rank", "R1"), "#000000"),
                        m.get("Size", (3, 3)),
                        unique=True,
                        avatar=m.get("Avatar")
                    )
                )
                if not hasattr(self, "alliance_member_images"):
                    self.alliance_member_images = []
                self.alliance_member_images.append(avatar_photo)
                
    def draw_grid(self):
        # Clear the entire canvas.
        self.canvas.delete("all")
        
        # Redraw terrain (unchanged)
        self.redraw_terrain()
        
        # Draw grid lines.
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
        
        # Draw both normal objects and markers in one unified call.
        self.redraw_objects()


    def on_marker_press(self, event):
        items = self.canvas.find_withtag("marker")
        for item in items:
            coords = self.canvas.coords(item)  # [x1, y1, x2, y2]
            if coords and coords[0] <= event.x <= coords[2] and coords[1] <= event.y <= coords[3]:
                self.current_marker_id = None
                for key, marker in self.markers.items():
                    adjusted = CELL_SIZE * self.zoom_factor
                    mx1 = marker["x1"] * adjusted + self.pan_x
                    my1 = (GRID_SIZE - marker["y1"]) * adjusted + self.pan_y
                    mx2 = marker["x2"] * adjusted + self.pan_x
                    my2 = (GRID_SIZE - marker["y2"]) * adjusted + self.pan_y
                    if abs(mx1 - coords[0]) < 5 and abs(my1 - coords[1]) < 5 and abs(mx2 - coords[2]) < 5 and abs(my2 - coords[3]) < 5:
                        self.current_marker_id = key
                        break
                self.marker_move_start = (event.x, event.y)
                if self.current_marker_id is not None:
                    marker = self.markers[self.current_marker_id]
                    x2 = marker["x2"] * adjusted + self.pan_x
                    y2 = (GRID_SIZE - marker["y2"]) * adjusted + self.pan_y
                    if abs(event.x - x2) < 10 and abs(event.y - y2) < 10:
                        self.marker_resizing = True
                    else:
                        self.marker_resizing = False
                # Prevent further propagation so that on_left_button_press doesn't run:
                return "break"

    def on_marker_motion(self, event):
        if self.current_marker_id is None:
            return
        # A movement indicates dragging.
        self.marker_dragging = True
        dx = event.x - self.marker_move_start[0]
        dy = event.y - self.marker_move_start[1]
        adjusted = CELL_SIZE * self.zoom_factor
        marker = self.markers[self.current_marker_id]
        # Convert the pixel delta to grid units.
        grid_dx = dx / adjusted
        grid_dy = dy / adjusted
        if self.marker_resizing:
            # Resize the marker (update bottom-right corner).
            marker["x2"] += grid_dx
            marker["y2"] -= grid_dy  # Remember: grid y increases upward.
        else:
            # Move the entire marker.
            marker["x1"] += grid_dx
            marker["y1"] -= grid_dy
            marker["x2"] += grid_dx
            marker["y2"] -= grid_dy
        self.marker_move_start = (event.x, event.y)
        self.draw_markers()



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

    def get_item_at(self, event):
        """
        Returns the key of the placed_objects entry under the mouse, or None if none.
        This single function checks both normal objects (center-based) and markers (bbox-based).
        """
        adjusted_cell_size = CELL_SIZE * self.zoom_factor
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        for key, data in self.placed_objects.items():
            if data.get("is_marker"):
                # This is a marker, stored as a bounding box (x1, y1, x2, y2) in the grid.
                x1, y1, x2, y2 = data["bbox"]
                # Convert marker’s bounding box from grid coords to canvas coords.
                c_x1 = x1 * adjusted_cell_size + self.pan_x
                c_y1 = (GRID_SIZE - y1) * adjusted_cell_size + self.pan_y
                c_x2 = x2 * adjusted_cell_size + self.pan_x
                c_y2 = (GRID_SIZE - y2) * adjusted_cell_size + self.pan_y
                # Check if mouse is within these canvas coords.
                if c_x1 <= canvas_x <= c_x2 and c_y1 <= canvas_y <= c_y2:
                    return key
            else:
                # This is a normal object, stored with a center (x, y) in the key and a size in data.
                (obj_x, obj_y) = key  # The grid center
                w, h = data.get("size", (3, 3))
                # Compute the bounding box in grid coords
                x_start = obj_x - w // 2
                y_start = obj_y - h // 2
                # Convert to canvas coords
                c_x1 = x_start * adjusted_cell_size + self.pan_x
                c_y1 = (GRID_SIZE - (y_start + h)) * adjusted_cell_size + self.pan_y
                c_x2 = c_x1 + w * adjusted_cell_size
                c_y2 = c_y1 + h * adjusted_cell_size
                if c_x1 <= canvas_x <= c_x2 and c_y1 <= canvas_y <= c_y2:
                    return key

        return None  # No item found under the mouse

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

    def edit_object_properties(self, old_name, category, current_color):
        """Opens a dialog to edit a placed object's properties.
        If no new name is entered, the old name is kept."""
        win = tk.Toplevel(self.root)
        win.title("Edit Object Properties")
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="Object Name:").grid(row=0, column=0, padx=10, pady=5)
        name_entry = tk.Entry(win)
        name_entry.insert(0, old_name)
        name_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(win, text="Object Color:").grid(row=1, column=0, padx=10, pady=5)
        color_label = tk.Label(win, text=current_color, bg=current_color, width=10)
        color_label.grid(row=1, column=1, padx=10, pady=5)
        
        def choose_color():
            color = colorchooser.askcolor(title="Choose Color")[1]
            if color:
                color_label.config(text=color, bg=color)
        tk.Button(win, text="Choose Color", command=choose_color).grid(row=1, column=2, padx=10, pady=5)
        
        def save_changes():
            new_name = name_entry.get().strip()
            if not new_name:
                new_name = old_name  # If no new name, keep the old one.
            new_color = color_label.cget("text")
            if category == "Friendly":
                self.friendly_objects.pop(old_name, None)
                self.friendly_objects[new_name] = new_color
                self.update_friendly_submenu()
            elif category == "Enemy":
                self.enemy_objects.pop(old_name, None)
                self.enemy_objects[new_name] = new_color
                self.update_enemy_submenu()
            else:
                self.other_objects.pop(old_name, None)
                self.other_objects[new_name] = new_color
                self.update_other_submenu()
            win.destroy()
        tk.Button(win, text="Save", command=save_changes).grid(row=2, column=0, columnspan=3, pady=10)
        win.wait_window(win)        

    def add_new_object(self, category):
        """Opens a dialog to add a new object in the specified category."""
        win = tk.Toplevel(self.root)
        win.title("Add New Object")
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="Object Name:").grid(row=0, column=0, padx=10, pady=5)
        name_entry = tk.Entry(win)
        name_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(win, text="Object Color:").grid(row=1, column=0, padx=10, pady=5)
        color_label = tk.Label(win, text="", bg="white", width=10)
        color_label.grid(row=1, column=1, padx=10, pady=5)
        
        def choose_color():
            color = colorchooser.askcolor(title="Choose Color")[1]
            if color:
                color_label.config(text=color, bg=color)
        tk.Button(win, text="Choose Color", command=choose_color).grid(row=1, column=2, padx=10, pady=5)
        
        def save_new():
            new_name = name_entry.get().strip()
            if not new_name:
                messagebox.showerror("Error", "Name cannot be empty.")
                return
            new_color = color_label.cget("text")
            if not new_color:
                # Set a default color if none chosen.
                new_color = "#FFFFFF"
            if category == "Friendly":
                self.friendly_objects[new_name] = new_color
                self.update_friendly_submenu()
            elif category == "Enemy":
                self.enemy_objects[new_name] = new_color
                self.update_enemy_submenu()
            else:
                self.other_objects[new_name] = new_color
                self.update_other_submenu()
            win.destroy()
        tk.Button(win, text="Add Object", command=save_new).grid(row=2, column=0, columnspan=3, pady=10)
        win.wait_window(win)

        def save_properties():
            new_tag = tag_entry.get().strip()
            new_color = color_display.cget("text")
            if not new_tag:
                messagebox.showerror("Error", "Name cannot be empty.")
                return
            # Update the object properties
            self.placed_objects[obj_center]["tag"] = new_tag
            self.placed_objects[obj_center]["color"] = new_color
            self.draw_grid()  # Redraw grid to update the object
            win.destroy()
        
        tk.Button(win, text="Save", command=save_properties).grid(row=2, column=0, columnspan=3, pady=10)

    def update_friendly_submenu(self):
        self.friendly_submenu.delete(0, tk.END)
        for name, color in self.friendly_objects.items():
            self.friendly_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))

    def update_enemy_submenu(self):
        self.enemy_submenu.delete(0, tk.END)
        for name, color in self.enemy_objects.items():
            self.enemy_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))

    def update_other_submenu(self):
        self.other_submenu.delete(0, tk.END)
        for name, color in self.other_objects.items():
            self.other_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))



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

    def show_object_context_menu(self, event, obj_center):
        """Opens a context menu for a placed object with options to edit, change type, or delete it."""
        context_win = tk.Toplevel(self.root)
        context_win.title("Object Options")
        tk.Label(context_win, text="Select an action:").pack(padx=10, pady=10)
        
        def delete_object():
            if obj_center in self.placed_objects:
                del self.placed_objects[obj_center]
                self.draw_grid()
            context_win.destroy()
                
        def edit_properties():
            context_win.destroy()
            self.edit_object_properties(obj_center)
        
        tk.Button(context_win, text="Edit Object", command=edit_properties).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(context_win, text="Change Type", command=change_type).pack(side=tk.LEFT, padx=10, pady=10)
        tk.Button(context_win, text="Delete Object", command=delete_object).pack(side=tk.RIGHT, padx=10, pady=10)

       
    def add_marker(self):
        """Opens a dialog to create a new marker and adds it to placed_objects."""
        win = tk.Toplevel(self.root)
        win.title("Add Marker")
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="Marker Name:").grid(row=0, column=0, padx=5, pady=5)
        name_entry = tk.Entry(win)
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(win, text="Marker Color:").grid(row=1, column=0, padx=5, pady=5)
        color_label = tk.Label(win, text="", bg="white", width=10)
        color_label.grid(row=1, column=1, padx=5, pady=5)
        def choose_color():
            color = colorchooser.askcolor(title="Choose Marker Color")[1]
            if color:
                color_label.config(text=color, bg=color)
        tk.Button(win, text="Choose Color", command=choose_color).grid(row=1, column=2, padx=5, pady=5)
        
        tk.Label(win, text="X1 (grid):").grid(row=2, column=0, padx=5, pady=5)
        x1_entry = tk.Entry(win)
        x1_entry.grid(row=2, column=1, padx=5, pady=5)
        tk.Label(win, text="Y1 (grid):").grid(row=3, column=0, padx=5, pady=5)
        y1_entry = tk.Entry(win)
        y1_entry.grid(row=3, column=1, padx=5, pady=5)
        tk.Label(win, text="X2 (grid):").grid(row=4, column=0, padx=5, pady=5)
        x2_entry = tk.Entry(win)
        x2_entry.grid(row=4, column=1, padx=5, pady=5)
        tk.Label(win, text="Y2 (grid):").grid(row=5, column=0, padx=5, pady=5)
        y2_entry = tk.Entry(win)
        y2_entry.grid(row=5, column=1, padx=5, pady=5)
        
        def save_marker():
            try:
                name = name_entry.get().strip()
                x1 = float(x1_entry.get())
                y1 = float(y1_entry.get())
                x2 = float(x2_entry.get())
                y2 = float(y2_entry.get())
            except Exception as e:
                messagebox.showerror("Error", "Invalid coordinates")
                return
            color = color_label.cget("text")
            if not name:
                messagebox.showerror("Error", "Name cannot be empty")
                return
            # Use a key like ("marker", name) and store a bounding box.
            key = ("marker", name)
            self.placed_objects[key] = {
                "is_marker": True,
                "tag": name,
                "color": color,    # This must be a valid hex color.
                "bbox": (x1, y1, x2, y2)
            }
            self.draw_grid()
            win.destroy()
        
        tk.Button(win, text="Save Marker", command=save_marker).grid(row=6, column=0, columnspan=3, pady=10)
        win.wait_window(win)

    def edit_marker(self, marker_key):
        """
        Opens a dialog to edit marker properties.
        marker_key is a tuple of the form ("marker", marker_name)
        """
        marker = self.placed_objects.get(marker_key)
        if not marker:
            return
        win = tk.Toplevel(self.root)
        win.title("Edit Marker")
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="Marker Name:").grid(row=0, column=0, padx=5, pady=5)
        name_entry = tk.Entry(win)
        name_entry.insert(0, marker["tag"])
        name_entry.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(win, text="Marker Color:").grid(row=1, column=0, padx=5, pady=5)
        color_label = tk.Label(win, text=marker["color"], bg=marker["color"], width=10)
        color_label.grid(row=1, column=1, padx=5, pady=5)
        def choose_color():
            color = colorchooser.askcolor(title="Choose Marker Color")[1]
            if color:
                color_label.config(text=color, bg=color)
        tk.Button(win, text="Choose Color", command=choose_color).grid(row=1, column=2, padx=5, pady=5)
        
        tk.Label(win, text="X1:").grid(row=2, column=0, padx=5, pady=5)
        x1_entry = tk.Entry(win)
        x1_entry.insert(0, marker["bbox"][0])
        x1_entry.grid(row=2, column=1, padx=5, pady=5)
        tk.Label(win, text="Y1:").grid(row=3, column=0, padx=5, pady=5)
        y1_entry = tk.Entry(win)
        y1_entry.insert(0, marker["bbox"][1])
        y1_entry.grid(row=3, column=1, padx=5, pady=5)
        tk.Label(win, text="X2:").grid(row=4, column=0, padx=5, pady=5)
        x2_entry = tk.Entry(win)
        x2_entry.insert(0, marker["bbox"][2])
        x2_entry.grid(row=4, column=1, padx=5, pady=5)
        tk.Label(win, text="Y2:").grid(row=5, column=0, padx=5, pady=5)
        y2_entry = tk.Entry(win)
        y2_entry.insert(0, marker["bbox"][3])
        y2_entry.grid(row=5, column=1, padx=5, pady=5)
        
        def save_changes():
            try:
                new_name = name_entry.get().strip()
                new_x1 = float(x1_entry.get())
                new_y1 = float(y1_entry.get())
                new_x2 = float(x2_entry.get())
                new_y2 = float(y2_entry.get())
            except Exception as e:
                messagebox.showerror("Error", "Invalid input")
                return
            new_color = color_label.cget("text")
            if not new_name:
                new_name = marker["tag"]
            # Update marker data.
            marker["tag"] = new_name
            marker["color"] = new_color
            marker["bbox"] = (new_x1, new_y1, new_x2, new_y2)
            # If the marker name changed, update the key in placed_objects.
            old_key = marker_key
            new_key = ("marker", new_name)
            if new_key != old_key:
                del self.placed_objects[old_key]
                self.placed_objects[new_key] = marker
            self.draw_grid()
            win.destroy()
        
        tk.Button(win, text="Save", command=save_changes).grid(row=6, column=0, columnspan=3, pady=10)
        win.wait_window(win)

    def edit_marker_prompt(self):
        """Opens a dialog to select a marker (from placed_objects) to edit."""
        # Gather all marker keys (which are tuples with first element "marker")
        marker_keys = [key for key in self.placed_objects if isinstance(key, tuple) and key[0] == "marker"]
        if not marker_keys:
            messagebox.showinfo("Info", "No markers to edit.")
            return
        win = tk.Toplevel(self.root)
        win.title("Select Marker to Edit")
        win.transient(self.root)
        win.grab_set()
        listbox = tk.Listbox(win)
        listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        # Insert marker names (second element of the key)
        for key in marker_keys:
            listbox.insert(tk.END, key[1])
        def select_marker():
            sel = listbox.curselection()
            if sel:
                marker_name = listbox.get(sel[0])
                key = ("marker", marker_name)
                win.destroy()
                self.edit_marker(key)
        tk.Button(win, text="Edit Selected Marker", command=select_marker).pack(pady=5)
        win.wait_window(win)

           
    def remove_marker_prompt(self):
        """Opens a dialog to select a marker (from placed_objects) to remove."""
        # Get keys that represent markers.
        marker_keys = [key for key in self.placed_objects if isinstance(key, tuple) and key[0] == "marker"]
        if not marker_keys:
            messagebox.showinfo("Info", "No markers to remove.")
            return
        win = tk.Toplevel(self.root)
        win.title("Remove Marker")
        win.transient(self.root)
        win.grab_set()
        marker_listbox = tk.Listbox(win)
        marker_listbox.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        for key in marker_keys:
            # key[1] is the marker name.
            marker_listbox.insert(tk.END, key[1])
        def delete_marker():
            sel = marker_listbox.curselection()
            if sel:
                marker_name = marker_listbox.get(sel[0])
                key = ("marker", marker_name)
                if key in self.placed_objects:
                    del self.placed_objects[key]
                    self.draw_grid()
                    win.destroy()
        tk.Button(win, text="Remove Selected Marker", command=delete_marker).pack(pady=5)
        win.wait_window(win)

    def activate_marker_drawing(self):
        self.current_tool = "marker_draw"
        self.top_right_status.config(text="Tool: Draw Marker")


    def marker_draw_press(self, event):
        if self.current_tool != "marker_draw":
            return
        # Record the initial canvas coordinates
        self.marker_draw_start = (self.canvas.canvasx(event.x),
                                  self.canvas.canvasy(event.y))
        # Create the temp rectangle with a solid outline (no dash)
        self.marker_draw_rect = self.canvas.create_rectangle(
            self.marker_draw_start[0],
            self.marker_draw_start[1],
            self.marker_draw_start[0],
            self.marker_draw_start[1],
            outline="green",   # or any color you like
            width=3,
            dash=()            # empty tuple = no dash
        )

    def marker_draw_motion(self, event):
        if self.current_tool != "marker_draw":
            return
        if self.marker_draw_rect is None:
            return
        
        # Current mouse position in canvas coords
        current_x = self.canvas.canvasx(event.x)
        current_y = self.canvas.canvasy(event.y)
        
        # Convert both 'start' and 'current' canvas coords -> snapped grid coords
        adjusted = CELL_SIZE * self.zoom_factor
        
        # Convert the start point
        start_cx, start_cy = self.marker_draw_start
        start_grid_x = int(round((start_cx - self.pan_x) / adjusted))
        start_grid_y = int(round(GRID_SIZE - (start_cy - self.pan_y) / adjusted - 1))

        # Convert the current drag point
        current_grid_x = int(round((current_x - self.pan_x) / adjusted))
        current_grid_y = int(round(GRID_SIZE - (current_y - self.pan_y) / adjusted - 1))
        
        # Now convert those grid coords back to canvas coords, so the rectangle
        # is drawn exactly on integer cell boundaries.
        c_x1 = start_grid_x * adjusted + self.pan_x
        c_y1 = (GRID_SIZE - start_grid_y) * adjusted + self.pan_y
        c_x2 = current_grid_x * adjusted + self.pan_x
        c_y2 = (GRID_SIZE - current_grid_y) * adjusted + self.pan_y
        
        # Update the rectangle's coords to reflect snapped positions
        self.canvas.coords(self.marker_draw_rect, c_x1, c_y1, c_x2, c_y2)
        # Also ensure its style is solid (no dash)
        self.canvas.itemconfig(self.marker_draw_rect, dash=(), outline="green")

 
    def marker_draw_release(self, event):
        if self.current_tool != "marker_draw" or self.marker_draw_rect is None:
            return

        coords = self.canvas.coords(self.marker_draw_rect)
        self.canvas.delete(self.marker_draw_rect)
        self.marker_draw_rect = None

        # Convert the canvas coordinates to grid coordinates
        adjusted = CELL_SIZE * self.zoom_factor
        raw_x1 = (coords[0] - self.pan_x) / adjusted
        raw_y1 = (coords[1] - self.pan_y) / adjusted
        raw_x2 = (coords[2] - self.pan_x) / adjusted
        raw_y2 = (coords[3] - self.pan_y) / adjusted

        # Round and flip Y (since your grid uses (GRID_SIZE - y) in the code)
        x1 = int(round(raw_x1))
        y1 = int(round(GRID_SIZE - raw_y1 - 1))
        x2 = int(round(raw_x2))
        y2 = int(round(GRID_SIZE - raw_y2 - 1))

        # Ensure x1 <= x2 and y1 <= y2
        if x2 < x1:
            x1, x2 = x2, x1
        if y2 < y1:
            y1, y2 = y2, y1

        # Compute width and height in grid cells
        width = x2 - x1 + 1
        height = y2 - y1 + 1

        # Compute the center where to store the object
        center_x = x1 + (width // 2)
        center_y = y1 + (height // 2)

        # Create a new normal object (instead of a "marker")
        tag = f"Rect_{center_x}_{center_y}"
        self.placed_objects[(center_x, center_y)] = {
            "tag": tag,
            "color": "gray",
            "size": (width, height)
        }

        self.draw_grid()

        # Optionally reset tool
        self.current_tool = None
        self.top_right_status.config(text="Tool: None")

    def prompt_marker_details(self, x1, y1, x2, y2):
        win = tk.Toplevel(self.root)
        win.title("Define Marker")
        win.transient(self.root)
        win.grab_set()
        
        tk.Label(win, text="Marker Name:").grid(row=0, column=0, padx=10, pady=5)
        name_entry = tk.Entry(win)
        name_entry.grid(row=0, column=1, padx=10, pady=5)
        
        tk.Label(win, text="Marker Color:").grid(row=1, column=0, padx=10, pady=5)
        color_label = tk.Label(win, text="black", bg="black", width=10)
        color_label.grid(row=1, column=1, padx=10, pady=5)
        def choose_color():
            color = colorchooser.askcolor(title="Choose Marker Color")[1]
            if color:
                color_label.config(text=color, bg=color)
        tk.Button(win, text="Choose Color", command=choose_color).grid(row=1, column=2, padx=10, pady=5)
        
        def save_marker():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Name cannot be empty.")
                return
            marker = {"name": name, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "color": color_label.cget("text")}
            self.placed_objects[("marker", name)] = marker
            self.draw_markers()
            win.destroy()
        tk.Button(win, text="Save Marker", command=save_marker).grid(row=2, column=0, columnspan=3, pady=10)
        win.wait_window(win)


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
        adjusted = CELL_SIZE * self.zoom_factor
        
        # Iterate over every placed object
        for key, data in self.placed_objects.items():
            if data.get("is_marker"):
                # It's a marker. It stores its geometry as a bounding box.
                x1, y1, x2, y2 = data["bbox"]
                # Convert grid coordinates to canvas coordinates.
                c_x1 = x1 * adjusted + self.pan_x
                c_y1 = (GRID_SIZE - y1) * adjusted + self.pan_y
                c_x2 = x2 * adjusted + self.pan_x
                c_y2 = (GRID_SIZE - y2) * adjusted + self.pan_y
                
                # Use a blue outline if selected, otherwise use its defined color.
                if key in self.selected_objects:
                    outline_color = "blue"
                    width = 4
                    dash = (4, 2)
                else:
                    outline_color = data["color"]
                    width = 4
                    dash = None
                
                self.canvas.create_rectangle(c_x1, c_y1, c_x2, c_y2,
                                             outline=outline_color, width=width, dash=dash, fill="")
                # Optionally, display the marker's name when zoomed out.
                if adjusted < self.grid_zoom_threshold:
                    mid_x = (c_x1 + c_x2) / 2
                    mid_y = (c_y1 + c_y2) / 2
                    self.canvas.create_text(mid_x, mid_y, text=data["tag"], fill=data["color"])
            else:
                # It's a normal object. Its key is a tuple (x, y) indicating its center, and it stores a "size".
                (obj_x, obj_y) = key
                w, h = data.get("size", (3, 3))
                x_start = obj_x - w // 2
                y_start = obj_y - h // 2
                c_x1 = x_start * adjusted + self.pan_x
                c_y1 = (GRID_SIZE - (y_start + h)) * adjusted + self.pan_y
                
                # Draw selection outline if selected.
                if key in self.selected_objects:
                    self.canvas.create_rectangle(c_x1, c_y1, c_x1 + w * adjusted, c_y1 + h * adjusted,
                                                 outline="red", width=3, dash=(4, 2))
                # If an avatar exists, attempt to draw it; otherwise draw a filled rectangle.
                if data.get("avatar") and os.path.exists(data["avatar"]):
                    try:
                        img = Image.open(data["avatar"])
                        img = img.resize((int(w * adjusted), int(h * adjusted)), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self.canvas.create_image(c_x1, c_y1, image=photo, anchor="nw")
                        if not hasattr(self, "object_images"):
                            self.object_images = []
                        self.object_images.append(photo)
                    except Exception as e:
                        # Fall back to a colored rectangle if the image fails.
                        self.canvas.create_rectangle(c_x1, c_y1, c_x1 + w * adjusted, c_y1 + h * adjusted,
                                                     fill=data["color"], outline="black")
                        self.canvas.create_text(c_x1 + (w * adjusted) / 2, c_y1 + (h * adjusted) / 2,
                                                 text=data["tag"], fill="white",
                                                 font=("Arial", int(adjusted / 3)))
                else:
                    self.canvas.create_rectangle(c_x1, c_y1, c_x1 + w * adjusted, c_y1 + h * adjusted,
                                                 fill=data["color"], outline="black")
                    self.canvas.create_text(c_x1 + (w * adjusted) / 2, c_y1 + (h * adjusted) / 2,
                                             text=data["tag"], fill="white",
                                             font=("Arial", int(adjusted / 3)))

    def delete_selected_objects(self, event):
        for key in list(self.selected_objects):
            if key in self.placed_objects:
                del self.placed_objects[key]
        self.selected_objects.clear()
        self.draw_grid()


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
        
        def on_add():
            name = name_var.get().strip()
            if not name:
                tk.messagebox.showerror("Error", "Name cannot be empty.")
                return
            # Automatically check in the "images" folder for an image file matching the name.
            avatar_path = self.get_alliance_avatar(name)
            new_member = {
                "Name": name,
                "Rank": rank_var.get(),
                "Avatar": avatar_path if avatar_path is not None else self.alliance_default_colors.get(rank_var.get(), "#000000")
            }
            self.alliance_members.append(new_member)
            self.alliance_members_changed = True
            self.update_member_listbox()
            self.update_alliance_members_submenu()
            add_win.destroy()
        
        tk.Button(add_win, text="Add Member", command=on_add).grid(row=2, column=0, columnspan=2, pady=10)

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
            self.update_alliance_members_submenu()
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
        
        # Add an option to edit placeable objects
        place_menu.add_command(label="Edit Placeable Objects", command=self.edit_placeable_objects)
        
        # Alliance submenu (if desired)
        self.create_object_submenu(place_menu, "Alliance", {
            "R1": "#2C3E50", "R2": "#34495E", "R3": "#5D6D7E", "R4": "#2874A6", "R5": "#1F618D"
        })
        
        # Friendly submenu using stored objects:
        self.friendly_submenu = tk.Menu(place_menu, tearoff=0)
        place_menu.add_cascade(label="Friendly", menu=self.friendly_submenu)
        for name, color in self.friendly_objects.items():
            self.friendly_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))
        
        # Enemy submenu:
        self.enemy_submenu = tk.Menu(place_menu, tearoff=0)
        place_menu.add_cascade(label="Enemy", menu=self.enemy_submenu)
        for name, color in self.enemy_objects.items():
            self.enemy_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))
        
        # Other submenu:
        self.other_submenu = tk.Menu(place_menu, tearoff=0)
        place_menu.add_cascade(label="Other", menu=self.other_submenu)
        for name, color in self.other_objects.items():
            self.other_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))
        
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

        self.canvas.bind("<Motion>", self.on_canvas_hover, add="+")
        
        markers_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Markers", menu=markers_menu)
        markers_menu.add_command(label="Draw Marker", command=self.activate_marker_drawing)
        markers_menu.add_command(label="Edit Marker", command=self.edit_marker_prompt)
        markers_menu.add_command(label="Remove Marker", command=self.remove_marker_prompt)

        
        
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

        self.top_right_status = tk.Label(self.root, text="Tool: None", font=("Arial", 10), bg="lightgray")
        self.top_right_status.place(relx=1.0, rely=0.0, anchor="ne", x=-5, y=5)

    
    def edit_placeable_objects(self):
        """Opens a dialog to edit the default (placeable) objects in the Friendly or Enemy category."""
        win = tk.Toplevel(self.root)
        win.title("Edit Placeable Objects")
        
        # Category selection: Friendly or Enemy
        tk.Label(win, text="Select Category:").grid(row=0, column=0, padx=10, pady=5)
        category_var = tk.StringVar(value="Friendly")
        tk.Radiobutton(win, text="Friendly", variable=category_var, value="Friendly").grid(row=0, column=1, padx=5, pady=5)
        tk.Radiobutton(win, text="Enemy", variable=category_var, value="Enemy").grid(row=0, column=2, padx=5, pady=5)
        
        # Listbox to show current objects in the selected category
        tk.Label(win, text="Select Object:").grid(row=1, column=0, padx=10, pady=5)
        object_listbox = tk.Listbox(win, height=5)
        object_listbox.grid(row=1, column=1, columnspan=2, padx=10, pady=5, sticky="we")
        
        def populate_listbox():
            object_listbox.delete(0, tk.END)
            cat = category_var.get()
            if cat == "Friendly":
                for key in self.friendly_objects.keys():
                    object_listbox.insert(tk.END, key)
            else:
                for key in self.enemy_objects.keys():
                    object_listbox.insert(tk.END, key)
        
        populate_listbox()
        
        # Update listbox when category changes
        category_var.trace("w", lambda *args: populate_listbox())
        
        # Entry for new name
        tk.Label(win, text="New Name:").grid(row=2, column=0, padx=10, pady=5)
        name_entry = tk.Entry(win)
        name_entry.grid(row=2, column=1, padx=10, pady=5, sticky="we")
        
        # Color selection
        tk.Label(win, text="New Color:").grid(row=3, column=0, padx=10, pady=5)
        color_label = tk.Label(win, text="", bg="white", width=10)
        color_label.grid(row=3, column=1, padx=10, pady=5)
        def choose_color():
            color = colorchooser.askcolor(title="Choose Color")[1]
            if color:
                color_label.config(text=color, bg=color)
        tk.Button(win, text="Choose Color", command=choose_color).grid(row=3, column=2, padx=10, pady=5)
        
        def save_changes():
            selected = object_listbox.curselection()
            if not selected:
                messagebox.showerror("Error", "No object selected.")
                return
            old_key = object_listbox.get(selected[0])
            new_key = name_entry.get().strip()
            new_color = color_label.cget("text")
            if not new_key:
                messagebox.showerror("Error", "Name cannot be empty.")
                return
            cat = category_var.get()
            if cat == "Friendly":
                # Remove old key and add new key with new color
                self.friendly_objects.pop(old_key, None)
                self.friendly_objects[new_key] = new_color
                self.update_friendly_submenu()
            else:
                self.enemy_objects.pop(old_key, None)
                self.enemy_objects[new_key] = new_color
                self.update_enemy_submenu()
            win.destroy()
        
        tk.Button(win, text="Save Changes", command=save_changes).grid(row=4, column=0, columnspan=3, pady=10)

    def update_friendly_submenu(self):
        """Rebuilds the Friendly submenu based on self.friendly_objects."""
        self.friendly_submenu.delete(0, tk.END)
        for name, color in self.friendly_objects.items():
            self.friendly_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))

    def update_enemy_submenu(self):
        """Rebuilds the Enemy submenu based on self.enemy_objects."""
        self.enemy_submenu.delete(0, tk.END)
        for name, color in self.enemy_objects.items():
            self.enemy_submenu.add_command(label=name, command=lambda n=name, c=color: self.activate_preset_object(n, c))

    def on_left_button_press(self, event):
        if self.current_tool == "marker_draw":
            self.marker_draw_press(event)
        else:
            if self.selected_tool and self.selected_tool.get("type") == "object":
                self.place_element(event)

            # Otherwise, proceed with normal selection/move/rectangle selection:
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            item_key = self.get_item_at(event)
            if item_key is not None:
                # (Selection / movement code here.)
                if item_key not in self.selected_objects:
                    self.selected_objects.clear()
                    self.selected_objects.add(item_key)
                    self.original_positions = {}
                    data = self.placed_objects[item_key]
                    if data.get("is_marker"):
                        self.original_positions[item_key] = data["bbox"]
                    else:
                        self.original_positions[item_key] = item_key
                else:
                    if not self.original_positions:
                        self.original_positions = {}
                        for key in self.selected_objects:
                            data = self.placed_objects[key]
                            if data.get("is_marker"):
                                self.original_positions[key] = data["bbox"]
                            else:
                                self.original_positions[key] = key
                self.moving_start = (x, y)
            else:
                # No object was clicked – start a rectangle selection.
                self.selected_objects.clear()
                self.selection_start = (x, y)
                self.selection_rect = self.canvas.create_rectangle(x, y, x, y,
                                                                   outline="red", dash=(2,2))


    def on_left_button_motion(self, event):
        # If the marker-drawing tool is active, use marker_draw_motion and skip normal logic:
        if self.current_tool == "marker_draw":
            self.marker_draw_motion(event)
            return  # Stop here so we don't also do selection/move code
        
        # Otherwise, do the normal selection/move code:
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # If we started moving an item...
        if self.moving_start is not None:
            dx = x - self.moving_start[0]
            dy = y - self.moving_start[1]
            adjusted = CELL_SIZE * self.zoom_factor
            grid_dx = dx / adjusted
            grid_dy = dy / adjusted

            for key in list(self.selected_objects):
                data = self.placed_objects[key]
                original = self.original_positions[key]
                if data.get("is_marker"):
                    # For markers, update the bounding box
                    x1, y1, x2, y2 = original
                    new_bbox = (x1 + grid_dx, y1 - grid_dy, x2 + grid_dx, y2 - grid_dy)
                    data["bbox"] = new_bbox
                else:
                    # For normal objects, update their center
                    orig_x, orig_y = original
                    new_x = orig_x + grid_dx
                    new_y = orig_y - grid_dy
                    new_center = (int(round(new_x)), int(round(new_y)))

                    # Update placed_objects
                    del self.placed_objects[key]
                    self.placed_objects[new_center] = data
                    
                    # Update selection & original_positions
                    self.selected_objects.remove(key)
                    self.selected_objects.add(new_center)
                    self.original_positions[new_center] = (new_x, new_y)

            self.moving_start = (x, y)
            self.draw_grid()
        
        # Else if we’re rubberbanding a rectangle for multi-selection,
        # just update the selection rectangle’s coords.
        elif self.selection_rect is not None:
            self.canvas.coords(self.selection_rect,
                               self.selection_start[0],
                               self.selection_start[1],
                               x, y)

    def on_left_button_release(self, event):
        if self.moving_start is not None:
            # Movement finished; clear moving variables.
            self.moving_start = None
            self.original_positions.clear()
        elif self.selection_rect is not None:
            # Finalize rectangle selection.
            x1, y1, x2, y2 = self.canvas.coords(self.selection_rect)
            # Normalize coordinates.
            if x1 > x2:
                x1, x2 = x2, x1
            if y1 > y2:
                y1, y2 = y2, y1
            adjusted = CELL_SIZE * self.zoom_factor
            selected_keys = []
            for key, data in self.placed_objects.items():
                if data.get("is_marker"):
                    # For markers, get canvas coordinates from the bounding box.
                    bx1, by1, bx2, by2 = data["bbox"]
                    c_bx1 = bx1 * adjusted + self.pan_x
                    c_by1 = (GRID_SIZE - by1) * adjusted + self.pan_y
                    c_bx2 = bx2 * adjusted + self.pan_x
                    c_by2 = (GRID_SIZE - by2) * adjusted + self.pan_y
                    # If the marker’s entire rectangle lies within the selection rectangle, select it.
                    if c_bx1 >= x1 and c_by1 >= y1 and c_bx2 <= x2 and c_by2 <= y2:
                        selected_keys.append(key)
                else:
                    # For normal objects, key is the center; compute the object's canvas bounding box.
                    obj_x, obj_y = key
                    w, h = data.get("size", (3, 3))
                    x_start = obj_x - w // 2
                    y_start = obj_y - h // 2
                    c_x1 = x_start * adjusted + self.pan_x
                    c_y1 = (GRID_SIZE - (y_start + h)) * adjusted + self.pan_y
                    c_x2 = c_x1 + w * adjusted
                    c_y2 = c_y1 + h * adjusted
                    if c_x1 >= x1 and c_y1 >= y1 and c_x2 <= x2 and c_y2 <= y2:
                        selected_keys.append(key)
            self.selected_objects = set(selected_keys)
            self.canvas.delete(self.selection_rect)
            self.selection_rect = None
            self.draw_grid()

    def get_marker_nearby(self, event, tolerance=10):
        """Return the marker dict if the mouse is within tolerance pixels of a marker's rectangle; otherwise None."""
        adjusted = CELL_SIZE * self.zoom_factor
        for marker in self.markers.values():
            x1 = marker["x1"] * adjusted + self.pan_x
            y1 = (GRID_SIZE - marker["y1"]) * adjusted + self.pan_y
            x2 = marker["x2"] * adjusted + self.pan_x
            y2 = (GRID_SIZE - marker["y2"]) * adjusted + self.pan_y
            # Expand the rectangle by tolerance on all sides.
            if (x1 - tolerance) <= event.x <= (x2 + tolerance) and (y1 - tolerance) <= event.y <= (y2 + tolerance):
                return marker
        return None

    def on_marker_press(self, event):
        # Get the top item under the pointer using the "current" tag.
        current_items = self.canvas.find_withtag("current")
        for item in current_items:
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("marker_"):
                    # Extract the marker's unique ID (its name)
                    marker_id = tag.split("_", 1)[1]
                    self.current_marker_id = marker_id
                    self.marker_move_start = (event.x, event.y)
                    adjusted = CELL_SIZE * self.zoom_factor
                    marker = self.markers[self.current_marker_id]
                    # Check if the click is near the bottom-right corner (for resizing)
                    x2 = marker["x2"] * adjusted + self.pan_x
                    y2 = (GRID_SIZE - marker["y2"]) * adjusted + self.pan_y
                    if abs(event.x - x2) < 10 and abs(event.y - y2) < 10:
                        self.marker_resizing = True
                    else:
                        self.marker_resizing = False
                    self.marker_dragging = False  # Reset dragging flag on press.
                    return "break"
                    
    def get_object_info(self, event):
        """
        Returns a string with information about the object (or marker) under the cursor.
        Checks markers first, then placed objects.
        """
        marker = self.get_marker_nearby(event, tolerance=10)
        if marker:
            return f"Marker: {marker['name']}\nCoords: {marker['x1']},{marker['y1']} - {marker['x2']},{marker['y2']}\nColor: {marker['color']}"
        obj_key = self.get_object_at(event)
        if obj_key:
            data = self.placed_objects.get(obj_key)
            if data:
                return f"Object: {data.get('tag', 'Unnamed')}\nColor: {data.get('color', 'N/A')}"
        return None

    def show_tooltip(self, text, x, y):
        # If a tooltip already exists with the same text, just update its position.
        if hasattr(self, 'tooltip') and self.tooltip is not None:
            current_text = self.tooltip_label.cget("text") if hasattr(self, 'tooltip_label') else ""
            if current_text == text:
                self.tooltip.wm_geometry(f"+{x+20}+{y+20}")
                return
            else:
                self.tooltip.destroy()
                self.tooltip = None
        # Create a new tooltip
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.wm_overrideredirect(True)  # Remove window decorations.
        self.tooltip.wm_geometry(f"+{x+20}+{y+20}")
        self.tooltip_label = tk.Label(self.tooltip, text=text, background="yellow",
                                      relief="solid", borderwidth=1, font=("Arial", 10))
        self.tooltip_label.pack(ipadx=1)

    def hide_tooltip(self):
        if hasattr(self, 'tooltip') and self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None

    def on_canvas_hover(self, event):
        # Check if the mouse is over the tooltip; if so, do nothing.
        if hasattr(self, 'tooltip') and self.tooltip is not None:
            tx = self.tooltip.winfo_rootx()
            ty = self.tooltip.winfo_rooty()
            tw = self.tooltip.winfo_width()
            th = self.tooltip.winfo_height()
            if tx <= event.x_root <= tx + tw and ty <= event.y_root <= ty + th:
                return
        info = self.get_object_info(event)
        if info:
            self.show_tooltip(info, event.x_root, event.y_root)
        else:
            self.hide_tooltip()


    def marker_draw_cancel(self, event):
        if self.current_tool == "marker_draw":
            if self.marker_draw_rect is not None:
                self.canvas.delete(self.marker_draw_rect)
                self.marker_draw_rect = None
            self.current_tool = None
            self.top_right_status.config(text="Tool: None")


    def handle_right_click(self, event):
        # If the marker drawing tool is active, cancel marker drawing.
        if self.current_tool == "marker_draw":
            self.marker_draw_cancel(event)
            return "break"

        # If any objects are currently selected, clear the selection and redraw.
        if self.selected_objects:
            self.selected_objects.clear()
            self.draw_grid()
            return "break"

        # Otherwise, check if a placed object was right-clicked.
        adjusted = CELL_SIZE * self.zoom_factor
        x = int((self.canvas.canvasx(event.x) - self.pan_x) / adjusted)
        y = GRID_SIZE - int((self.canvas.canvasy(event.y) - self.pan_y) / adjusted) - 1

        found_obj = None
        for center, data in self.placed_objects.items():
            w, h = data.get("size", (3, 3))
            cx, cy = center
            x_start = cx - w // 2
            y_start = cy - h // 2
            if x_start <= x < x_start + w and y_start <= y < y_start + h:
                found_obj = center
                break

        if found_obj is not None:
            self.show_object_context_menu(event, found_obj)
            return "break"
        else:
            self.deselect_tool(event)
            return "break"

    def get_alliance_avatar(self, name):
        """Checks the 'images' folder for an image file with the same name as the member.
        Tries common image extensions. Returns the file path if found, or None otherwise."""
        extensions = [".png", ".jpg", ".jpeg", ".gif"]
        for ext in extensions:
            path = os.path.join("images", name + ext)
            if os.path.exists(path):
                return path
        return None


    def get_object_at(self, event):
        """Return the key (x, y) of the object under the mouse, or None if none."""
        adjusted = CELL_SIZE * self.zoom_factor
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        grid_x = int((canvas_x - self.pan_x) / adjusted)
        grid_y = GRID_SIZE - int((canvas_y - self.pan_y) / adjusted) - 1
        for (obj_x, obj_y), data in self.placed_objects.items():
            w, h = data.get("size", (3,3))
            x_start = obj_x - w // 2
            y_start = obj_y - h // 2
            if x_start <= grid_x < x_start + w and y_start <= grid_y < y_start + h:
                return (obj_x, obj_y)
        return None
        
    def delete_selected_objects(self, event):
        # Delete placed objects.
        for key in list(self.selected_objects):
            if key in self.placed_objects:
                del self.placed_objects[key]
        # Delete selected markers.
        for marker_id in list(self.selected_markers):
            if marker_id in self.markers:
                del self.markers[marker_id]
        self.selected_objects.clear()
        self.selected_markers.clear()
        self.draw_grid()


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

    def activate_preset_object(self, name, color, size=(3, 3), unique=False, avatar=None):
        # Instead of placing the object immediately,
        # set the selected tool so that the next click on the grid
        # will place the object.
        self.selected_tool = {
            "tag": name,
            "color": color,
            "size": size,
            "avatar": avatar,
            "type": "object",
            "unique": unique
        }
        self.status_bar.config(text=f"Tool: {name}")
        
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
