from dataclasses import dataclass
import math
from drafter import *

# ==========================================
# GLOBAL CONSTANTS (Allowed by requirements)
# ==========================================
RHO_STEEL = 7850.0       # Density of Rolled Homogeneous Armor (kg/m^3)
RHO_COPPER = 8960.0      # Density of copper HEAT liner (kg/m^3)
RHO_TUNGSTEN = 17500.0   # Density of tungsten APFSDS rod (kg/m^3)
RHO_AIR = 1.225          # Standard air density at sea level (kg/m^3)
DEMARRE_K = 0.00012      # Empirical DeMarre coefficient for APCBC
ARMOR_YIELD_PA = 1.5e9   # Approximate RHA yield strength (Pa)

# ==========================================
# DATACLASSES
# ==========================================
@dataclass
class Shell:
    name: str
    shell_type: str        # "APCBC", "APFSDS", or "HEAT"
    mass: float            # kg
    diameter: float        # meters
    muzzle_velocity: float # m/s
    length: float          # meters (rod or liner length)

@dataclass
class Target:
    thickness_mm: float
    angle_deg: float
    has_era: bool

@dataclass
class State:
    # Requirement: At least 4 fields, including a list/dict of class instances,
    # all 4 meaningfully modified across routes.
    active_shell: Shell
    arsenal: list[Shell]
    target: Target
    simulation_distance: float
    last_verdict: str

# ==========================================
# HELPER PHYSICS FUNCTIONS
# ==========================================
def calculate_velocity_decay(shell: Shell, distance: float) -> float:
    """Calculates projectile impact velocity after aerodynamic drag over distance."""
    if distance <= 0:
        return shell.muzzle_velocity
    area = math.pi * ((shell.diameter / 2.0) ** 2)
    drag_coeff = 0.18 if shell.shell_type == "APFSDS" else 0.28
    k = (RHO_AIR * drag_coeff * area) / (2.0 * shell.mass)
    return shell.muzzle_velocity * math.exp(-k * distance)

def calculate_penetration(shell: Shell, impact_velocity: float, has_era: bool) -> float:
    """Calculates raw flat RHA penetration in millimeters based on shell type."""
    # Meaningful If Statement #1: Branching ballistics equations by warhead type
    if shell.shell_type == "APCBC":
        # DeMarre semi-empirical kinetic formula
        energy_term = (shell.mass * (impact_velocity ** 2)) / (shell.diameter ** 3)
        pen_m = DEMARRE_K * (energy_term ** 0.7) * shell.diameter
        pen_mm = pen_m * 1000.0
    elif shell.shell_type == "APFSDS":
        # Simplified Odermatt long-rod hydrodynamic penetration
        rod_length_mm = shell.length * 1000.0
        density_ratio = math.sqrt(RHO_TUNGSTEN / RHO_STEEL)
        velocity_factor = math.exp(-ARMOR_YIELD_PA / (RHO_TUNGSTEN * (impact_velocity ** 2)))
        pen_mm = rod_length_mm * density_ratio * velocity_factor
    else:
        # Birkhoff hydrodynamic equation for HEAT shaped charges (velocity independent)
        jet_length_mm = shell.length * 1000.0 * 3.5
        pen_mm = jet_length_mm * math.sqrt(RHO_COPPER / RHO_STEEL)

    # Apply Explosive Reactive Armor (ERA) degradation
    if has_era:
        if shell.shell_type == "HEAT":
            pen_mm *= 0.45  # ERA severely disrupts shaped-charge jets
        else:
            pen_mm *= 0.80  # Heavy ERA reduces kinetic penetrator performance

    return pen_mm

def evaluate_shot(shell: Shell, target: Target, distance: float) -> tuple[float, float, float, str]:
    """Runs full terminal ballistics evaluation and returns (v_impact, pen_mm, los_mm, verdict)."""
    v_impact = calculate_velocity_decay(shell, distance)
    pen_mm = calculate_penetration(shell, v_impact, target.has_era)
    
    # Prevent division by zero at 90 degrees
    clamped_angle = min(max(target.angle_deg, 0.0), 85.0)
    los_mm = target.thickness_mm / math.cos(math.radians(clamped_angle))

    # Meaningful If Statement #2: Ricochet angle check
    if clamped_angle > 72.0 and shell.shell_type != "HEAT":
        verdict = "RICOCHET (Impact angle exceeded 72 degrees)"
    # Meaningful If Statement #3: Armor defeat comparison
    elif pen_mm >= los_mm:
        margin = pen_mm - los_mm
        verdict = f"PENETRATION SUCCESSFUL (+{margin:.1f} mm overpenetration)"
    else:
        deficit = los_mm - pen_mm
        verdict = f"ARMOR STOPPED ROUND (-{deficit:.1f} mm short)"

    return v_impact, pen_mm, los_mm, verdict

# ==========================================
# ROUTES & PAGES (11 Routes, 7 Distinct Pages)
# ==========================================

# --- PAGE 1: HOME DASHBOARD ---
@route
def index(state: State) -> Page:
    era_status = "Enabled" if state.target.has_era else "Disabled"
    return Page(state, [
        Header("Tank Ballistics & Terminal Penetration Simulator"),
        Text("Configure tank ammunition, adjust target armor parameters, and run physics simulations."),
        LineBreak(),
        Header("Current Session Loadout", 2),
        Text(f"Active Shell: {state.active_shell.name} ({state.active_shell.shell_type})"),
        "\n",
        Text(f"Target Profile: {state.target.thickness_mm:.0f} mm RHA @ {state.target.angle_deg:.0f}° | ERA: {era_status}"),
        "\n",
        Text(f"Engagement Range: {state.simulation_distance:.0f} m"),
        "\n",
        Text(f"Last Simulation Result: {state.last_verdict}"),
        LineBreak(),
        Button("1. Manage Shell Arsenal", show_arsenal),
        Button("2. Configure Target Armor", target_config),
        Button("3. Run Ballistics Simulator", simulate_page),
        Button("4. Compare Entire Arsenal", compare_arsenal),
        Button("5. Mission Summary Report", summary_report)
    ])

# --- PAGE 2: SHELL ARSENAL INVENTORY ---
@route
def show_arsenal(state: State) -> Page:
    rows = [["Shell Name", "Type", "Mass", "Caliber", "Muzzle Vel.", "Muzzle Energy", "Status"]]
    
    # Renamed loop variable from 'index' to 'i' so it doesn't overwrite the 'index' route function
    for i, shell in enumerate(state.arsenal):
        ke_mj = (0.5 * shell.mass * (shell.muzzle_velocity ** 2)) / 1_000_000.0
        if shell.name == state.active_shell.name:
            action_cell = "ACTIVE"
        else:
            action_cell = Button("Select", select_shell, arguments=Argument("shell_idx", i))
            
        rows.append([
            shell.name,
            shell.shell_type,
            f"{shell.mass:.1f} kg",
            f"{shell.diameter * 1000:.0f} mm",
            f"{shell.muzzle_velocity:.0f} m/s",
            f"{ke_mj:.2f} MJ",
            action_cell
        ])

    return Page(state, [
        Header("Tank Shell Arsenal"),
        Text("Select an active shell for simulation or add custom ammunition below."),
        Table(rows),
        LineBreak(),
        Button("+ Add Custom Shell", add_shell_page),
        Button("Back to Home", index)
    ])

@route
def select_shell(state: State, shell_idx: int) -> Page:
    idx = int(shell_idx)
    if 0 <= idx < len(state.arsenal):
        state.active_shell = state.arsenal[idx]
    return show_arsenal(state)

# --- PAGE 3: ADD CUSTOM SHELL FORM ---
@route
def add_shell_page(state: State) -> Page:
    return Page(state, [
        Header("Add Custom Tank Shell"),
        Text("Shell Name:"),
        TextBox("new_name", "120mm DM53"),
        Text("Warhead Type:"),
        SelectBox("new_type", ["APFSDS", "APCBC", "HEAT"], "APFSDS"),
        Text("Projectile Mass (kg):"),
        TextBox("new_mass", "8.35"),
        Text("Projectile Diameter (meters, e.g., 0.120):"),
        TextBox("new_diameter", "0.120"),
        Text("Muzzle Velocity (m/s):"),
        TextBox("new_velocity", "1750"),
        Text("Penetrator Rod / Liner Length (meters, e.g., 0.68):"),
        TextBox("new_length", "0.68"),
        LineBreak(),
        Button("Save Shell to Arsenal", save_shell),
        Button("Cancel", show_arsenal)
    ])

# --- ROUTE HANDLER: SAVE NEW SHELL (Modifies State Field #2) ---
@route
def save_shell(state: State, new_name: str, new_type: str, new_mass: str, 
               new_diameter: str, new_velocity: str, new_length: str) -> Page:
    # Basic validation to prevent crashes on invalid numeric strings
    try:
        mass_val = max(0.1, float(new_mass))
        diam_val = max(0.01, float(new_diameter))
        vel_val = max(50.0, float(new_velocity))
        len_val = max(0.05, float(new_length))
        clean_name = new_name.strip() if new_name.strip() else "Custom Round"
        
        custom_shell = Shell(
            name=clean_name,
            shell_type=new_type,
            mass=mass_val,
            diameter=diam_val,
            muzzle_velocity=vel_val,
            length=len_val
        )
        state.arsenal.append(custom_shell)
        state.active_shell = custom_shell
    except ValueError:
        pass  # Keep existing state if user enters non-numeric text
        
    return show_arsenal(state)

# --- PAGE 4: TARGET ARMOR CONFIGURATION ---
@route
def target_config(state: State) -> Page:
    return Page(state, [
        Header("Target Armor Configuration"),
        Text(f"Currently Testing Against: {state.active_shell.name}"),
        LineBreak(),
        Text("Base RHA Armor Thickness (mm):"),
        TextBox("armor_mm", str(state.target.thickness_mm)),
        "\n",
        Text("Armor Slope Angle (degrees from vertical, 0 to 85):"),
        TextBox("angle_deg", str(state.target.angle_deg)),
        CheckBox("has_era", state.target.has_era),
        Text("Equip Target with Explosive Reactive Armor (ERA)"),
        LineBreak(),
        Button("Apply Target Specs", update_target),
        Button("Back to Home", index)
    ])

# --- ROUTE HANDLER: UPDATE TARGET (Modifies State Field #3) ---
@route
def update_target(state: State, armor_mm: str, angle_deg: str, has_era: bool) -> Page:
    try:
        thick = max(1.0, float(armor_mm))
        angle = min(max(0.0, float(angle_deg)), 85.0)
        state.target = Target(thickness_mm=thick, angle_deg=angle, has_era=has_era)
    except ValueError:
        pass
    return simulate_page(state)

# --- PAGE 5: BALLISTICS SIMULATOR ---
@route
def simulate_page(state: State) -> Page:
    v_imp, pen, los, verdict = evaluate_shot(
        state.active_shell, state.target, state.simulation_distance
    )
    
    # Generate a quick multi-range reference table using a loop
    range_rows = [["Range (m)", "Impact Velocity", "Effective Penetration"]]
    for dist in [100, 500, 1000, 1500, 2000, 3000]:
        d_vel = calculate_velocity_decay(state.active_shell, float(dist))
        d_pen = calculate_penetration(state.active_shell, d_vel, state.target.has_era)
        range_rows.append([f"{dist} m", f"{d_vel:.0f} m/s", f"{d_pen:.1f} mm"])

    return Page(state, [
        Header("Terminal Ballistics Simulator"),
        Text(f"Active Shell: {state.active_shell.name} ({state.active_shell.shell_type})"),
        Text(f"Target Armor: {state.target.thickness_mm:.0f} mm @ {state.target.angle_deg:.0f}° (Line-of-Sight: {los:.1f} mm)"),
        LineBreak(),
        Text("Engagement Distance (meters):"),
        TextBox("dist_input", str(state.simulation_distance)),
        Button("Calculate Impact Physics", run_sim),
        LineBreak(),
        Header("Simulation Output", 2),
        Text(f"Velocity at Impact: {v_imp:.1f} m/s"),
        "\n",
        Text(f"Calculated Penetration: {pen:.1f} mm RHA"),
        "\n",
        Text(f"Outcome Verdict: {verdict}"),
        LineBreak(),
        Header("Penetration Drop-off by Distance", 2),
        Table(range_rows),
        LineBreak(),
        Button("Compare All Arsenal Shells", compare_arsenal),
        Button("Back to Home", index)
    ])

# --- ROUTE HANDLER: EXECUTE SIMULATION (Modifies State Fields #4 & #5) ---
@route
def run_sim(state: State, dist_input: str) -> Page:
    try:
        dist = max(0.0, float(dist_input))
        state.simulation_distance = dist
        _, _, _, verdict = evaluate_shot(state.active_shell, state.target, dist)
        state.last_verdict = verdict
    except ValueError:
        pass
    return simulate_page(state)

# --- PAGE 6: COMPARATIVE ARSENAL ANALYSIS ---
@route
def compare_arsenal(state: State) -> Page:
    rows = [["Shell Name", "Type", f"Penetration @ {state.simulation_distance:.0f}m", "Target LOS Armor", "Result"]]
    
    # Requirement: Loop over list of class instances to compare performance
    for shell in state.arsenal:
        _, pen, los, verdict = evaluate_shot(shell, state.target, state.simulation_distance)
        rows.append([
            shell.name,
            shell.shell_type,
            f"{pen:.1f} mm",
            f"{los:.1f} mm",
            verdict
        ])

    return Page(state, [
        Header("Comparative Arsenal Analysis"),
        Text(f"Testing all stored shells at {state.simulation_distance:.0f} meters."),
        Table(rows),
        LineBreak(),
        Button("Reconfigure Target", target_config),
        Button("View Mission Summary", summary_report),
        Button("Back to Home", index)
    ])

# --- PAGE 7: MISSION SUMMARY & RESET ---
@route
def summary_report(state: State) -> Page:
    v_imp, pen, los, verdict = evaluate_shot(
        state.active_shell, state.target, state.simulation_distance
    )
    velocity_loss = state.active_shell.muzzle_velocity - v_imp
    
    return Page(state, [
        Header("Ballistics Operational Summary"),
        Text(f"Total Shells in Arsenal: {len(state.arsenal)}"),
        "\n",
        Text(f"Selected Projectile: {state.active_shell.name} ({state.active_shell.shell_type})"),
        "\n",
        Text(f"Aerodynamic Velocity Loss: {velocity_loss:.1f} m/s over {state.simulation_distance:.0f} m"),
        "\n",
        Text(f"Effective Penetration: {pen:.1f} mm vs {los:.1f} mm Effective Armor"),
        "\n",
        Text(f"Final Assessment: {verdict}"),
        "\n",
        Button("Reset Simulator to Defaults", reset_state),
        Button("Return to Home", index)
    ])

# --- ROUTE HANDLER: RESET STATE ---
@route
def reset_state(state: State) -> Page:
    default_shells = create_default_arsenal()
    state.arsenal = default_shells
    state.active_shell = default_shells[0]
    state.target = Target(thickness_mm=450.0, angle_deg=60.0, has_era=False)
    state.simulation_distance = 1000.0
    state.last_verdict = "Not yet simulated"
    return index(state)

# ==========================================
# INITIALIZATION & SERVER START
# ==========================================
def create_default_arsenal() -> list[Shell]:
    return [
        Shell("120mm M829A2", "APFSDS", 7.9, 0.120, 1680.0, 0.65),
        Shell("120mm M830A1", "HEAT", 11.4, 0.120, 1140.0, 0.14),
        Shell("88mm PzGr. 39/43", "APCBC", 10.2, 0.088, 1000.0, 0.35),
        Shell("125mm 3BM42 Mango", "APFSDS", 7.05, 0.125, 1700.0, 0.57)
    ]

initial_arsenal = create_default_arsenal()
initial_state = State(
    active_shell=initial_arsenal[0],
    arsenal=initial_arsenal,
    target=Target(thickness_mm=450.0, angle_deg=60.0, has_era=False),
    simulation_distance=1000.0,
    last_verdict="Ready to simulate"
)

start_server(initial_state)
