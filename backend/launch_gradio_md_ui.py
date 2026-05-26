#!/usr/bin/env python3
"""
Simple Gradio UI launcher for MD simulation.
Provides a minimal interface to input a PDB ID and run a short MD simulation.
Run as: python launch_gradio_md_ui.py [port]
If no port is supplied, defaults to 7860.
"""
import sys
import os
import subprocess


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else "7860"
    # Assume md_simulation.py is in the same directory.
    script_path = os.path.join(os.path.dirname(__file__), "md_simulation.py")
    # Build the Gradio app inline.
    gradio_import = "import gradio as gr"
    # Write a temporary file that defines the Gradio interface.
    temp_file = os.path.join(os.path.dirname(__file__), "_gradio_app.py")
    with open(temp_file, "w") as f:
        f.write(f"""{gradio_import}\n""")
        f.write("def run_md(pdb_id, steps=5000):\n")
        f.write("    import subprocess, json, sys\n")
        f.write("    cmd = [sys.executable, script_path, pdb_id, str(steps)]\n")
        f.write("    out = subprocess.check_output(cmd)\n")
        f.write("    return json.loads(out.decode())\n")
        f.write("ui = gr.Interface(fn=run_md, inputs=[gr.Textbox(label='PDB ID'), gr.Number(label='Steps', value=5000)], outputs=gr.JSON())\n")
        f.write("ui.launch(server_name='0.0.0.0', server_port=int(port))\n")
    # Execute the temporary Gradio app.
    subprocess.run([sys.executable, temp_file])

if __name__ == "__main__":
    main()
