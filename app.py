from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
import subprocess
import psutil
import libvirt
import xml.etree.ElementTree as ET

app = Flask(__name__)

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# VM Table
class VMEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vm_name = db.Column(db.String(100), nullable=False)
    os_type = db.Column(db.String(50), nullable=False)
    memory = db.Column(db.Integer, nullable=False)
    cpus = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"<VM {self.vm_name}>"

# Home page
@app.route('/')
def index():
    return render_template('index.html')

# VM create endpoint
@app.route('/create-vm')
def create_vm():
    vm_name = request.args.get('vm_name')
    memory = request.args.get('memory')
    cpus = request.args.get('cpus')
    os_type = request.args.get('os')

    if not all([vm_name, memory, cpus, os_type]):
        return "❌ Error: Missing required fields."

    qcow2_map = {
        "ubuntu": "/var/lib/libvirt/images/1ubuntu.qcow2",
        "fedora": "/var/lib/libvirt/images/fedora-2.qcow2",
        "linuxmint": "/var/lib/libvirt/images/linuxmint-cinnamon.qcow2",
        "kali": "/var/lib/libvirt/images/kali-cloud.qcow2"
    }

    if os_type not in qcow2_map:
        return "❌ Error: Unsupported OS type."

    extra_vars = {
        "vm_name": vm_name,
        "vm_memory": memory,
        "vm_cpus": cpus,
        "os_type": os_type,
        "base_image": qcow2_map[os_type]
    }

    try:
        extra_vars_str = ' '.join(f'{k}="{v}"' for k, v in extra_vars.items())

        result = subprocess.run([
            "ansible-playbook",
            "-i", "ansible/inventory.ini",
            "ansible/create_vm.yml",
            "--extra-vars", extra_vars_str
        ], check=True, capture_output=True, text=True)

        new_vm = VMEntry(
            vm_name=vm_name,
            os_type=os_type,
            memory=int(memory),
            cpus=int(cpus)
        )
        db.session.add(new_vm)
        db.session.commit()

        return f"✅ VM '{vm_name}' with OS '{os_type}' created successfully"

    except subprocess.CalledProcessError as e:
        return f"❌ VM creation failed:<br><pre>{e.stderr}</pre>"

# 🔹 Fetch IP address using virsh domifaddr
def get_vm_ip(vm_name):
    try:
        result = subprocess.run(
            ["virsh", "domifaddr", vm_name, "--source", "agent"],
            capture_output=True, text=True
        )
        output = result.stdout

        for line in output.splitlines():
            if 'ipv4' in line or 'ipv6' in line:
                parts = line.split()
                if len(parts) >= 4:
                    return parts[3].split('/')[0]  # Remove CIDR
    except Exception as e:
        print(f"Error fetching IP for {vm_name}: {e}")
    return "N/A"

# 🔹 Get live VMs using libvirt and match with DB
def get_live_vms():
    vms = []
    try:
        conn = libvirt.open('qemu:///system')
        domains = conn.listAllDomains()

        db_vms = VMEntry.query.all()
        vm_os_map = {vm.vm_name: vm.os_type for vm in db_vms}

        for i, domain in enumerate(domains, start=1):
            vm_name = domain.name()
            is_active = domain.isActive()
            status = "Running" if is_active else "Shutoff"

            xml = domain.XMLDesc()
            root = ET.fromstring(xml)

            memory_elem = root.find('./memory')
            vcpu_elem = root.find('./vcpu')

            memory = int(memory_elem.text) // 1024 if memory_elem is not None else 0
            cpus = int(vcpu_elem.text) if vcpu_elem is not None else 0
            os_type = vm_os_map.get(vm_name, "Unknown")
            ip_address = get_vm_ip(vm_name)

            vms.append({
                'id': i,
                'vm_name': vm_name,
                'memory': memory,
                'cpus': cpus,
                'os': os_type,
                'status': status,
                'ip': ip_address
            })

        conn.close()
    except libvirt.libvirtError as e:
        print("Libvirt error:", e)
    return vms

# 🔹 Get system memory
def get_system_memory():
    mem = psutil.virtual_memory()
    return {
        'total': mem.total // (1024 * 1024),
        'used': mem.used // (1024 * 1024),
        'free': mem.available // (1024 * 1024)
    }

# 🔹 View VMs
@app.route('/view-database')
def view_database():
    db_vms = VMEntry.query.all()
    live_vms = get_live_vms()
    system_memory = get_system_memory()
    return render_template(
        'view_database.html',
        vms=live_vms,
        db_vms=db_vms,
        system_memory=system_memory
    )

# Run app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=8080)

