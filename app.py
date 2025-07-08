from flask import Flask, request, render_template
import subprocess

app = Flask(__name__)  # pehle yeh hona zaroori hai

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/create-vm')
def create_vm():
    vm_name = request.args.get('vm_name')
    os_type = request.args.get('os')
    memory = request.args.get('memory')
    cpus = request.args.get('cpus')

    iso_map = {
        "alpine": "/var/lib/libvirt/images/alpine.iso",
        "tinycore": "/var/lib/libvirt/images/tinycore.iso",
        "slitaz": "/var/lib/libvirt/images/slitaz.iso",  
        "antix": "/var/lib/libvirt/images/antix.iso"
    }

    iso_path = iso_map.get(os_type, "/var/lib/libvirt/images/alpine.iso")

    try:
        subprocess.run([
            "ansible-playbook", "-i", "ansible/inventory.ini", "ansible/create_vm.yml",
            "--extra-vars", f"vm_name={vm_name} vm_memory={memory} vm_cpus={cpus} iso_path={iso_path}"
        ], check=True)
        return f"✅ VM '{vm_name}' with {os_type} created successfully!"
    except subprocess.CalledProcessError as e:
        return f"❌ Error: {e}"

if __name__ == '__main__':
    app.run(debug=True)

