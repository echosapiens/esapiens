#!/usr/bin/env python3
"""
Simple OpenMM MD simulation script.
Usage: python md_simulation.py <PDB_ID> <steps>
"""
import sys
import json
from pathlib import Path

# Ensure OpenMM is installed in the environment.
try:
    from simtk import openmm, unit
    from simtk.openmm import app
except ImportError:
    # OpenMM may be under openmm package for newer versions.
    from openmm import *
    from openmm.app import *
    from openmm import unit


def download_pdb(pdb_id: str, out_dir: Path) -> Path:
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
    out_path = out_dir / f"{pdb_id.upper()}.pdb"
    # Use urllib which is allowed.
    from urllib.request import urlopen

    with urlopen(url) as resp, open(out_path, "wb") as f:
        f.write(resp.read())
    return out_path


def run_simulation(pdb_path: Path, steps: int = 5000):
    pdb = app.PDBFile(str(pdb_path))
    forcefield = app.ForceField("amber14-all.xml", "amber14/tip3p.xml")
    modeller = app.Modeller(pdb.topology, pdb.positions)
    modeller.addSolvent(forcefield, model="tip3p", padding=1.0 * unit.nanometers)

    system = forcefield.createSystem(
        modeller.topology,
        nonbondedMethod=app.PME,
        nonbondedCutoff=1.0 * unit.nanometers,
        constraints=app.HBonds,
    )
    integrator = openmm.LangevinIntegrator(
        300 * unit.kelvin, 1 / unit.picosecond, 0.002 * unit.picoseconds
    )
    platform = openmm.Platform.getPlatformByName("CPU")
    simulation = app.Simulation(modeller.topology, system, integrator, platform)
    simulation.context.setPositions(modeller.positions)
    simulation.minimizeEnergy()
    simulation.context.setVelocitiesToTemperature(300 * unit.kelvin)
    simulation.step(steps)
    state = simulation.context.getState(getEnergy=True, getPositions=True)
    energy = state.getPotentialEnergy().value_in_unit(unit.kilojoules_per_mole)
    return energy


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: md_simulation.py <PDB_ID> [steps]"}))
        sys.exit(1)
    pdb_id = sys.argv[1]
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    work_dir = Path.cwd()
    pdb_path = download_pdb(pdb_id, work_dir)
    energy = run_simulation(pdb_path, steps)
    result = {"pdb_id": pdb_id.upper(), "steps": steps, "energy_kJ_per_mol": energy}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
