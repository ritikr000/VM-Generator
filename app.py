from flask import Flask, request, render_template
from flask_sqlalchemy import SQLAlchemy
import subprocess

app = Flask(__name__)

# Configure SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///vms.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Define a model for VM entries
class VMEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vm_name = db.Column(db.String(100))
    os_type = db.Column(db.String(50))
    memory = db.Column(db.String(50))
    cpus = db.Column(db.String(10))

# Create the table if it doesn't exist
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/create-vm')
def create_vm():
    vm_name = request.args.get('vm_name')
    memory = request.args.get('memory')
    cpus = request.args.get('cpus')
    os_type = request.args.get('os')

    # ISO selection
    iso_map = {
        "fedora": "/var/lib/libvirt/images/fedora-full.iso",
        "slitaz": "/var/lib/libvirt/images/slitaz.iso",
        "tinycore": "/var/lib/libvirt/images/tinycore.iso",
        "alpine": "/var/lib/libvirt/images/alpine.iso",
        "ubuntu": "/var/lib/libvirt/images/ubuntu.iso"
    }

    iso_path = iso_map.get(os_type)
    if not all([vm_name, memory, cpus, iso_path]):
        return "❌ Error: Missing or invalid parameters."

    try:
        subprocess.run([
            "ansible-playbook", "-i", "ansible/inventory.ini", "ansible/create_vm.yml",
            "--extra-vars", f"vm_name={vm_name} vm_memory={memory} vm_cpus={cpus} iso_path={iso_path} os_type={os_type}"
        ], check=True)

        # Save to DB
        new_vm = VMEntry(vm_name=vm_name, os_type=os_type, memory=memory, cpus=cpus)
        db.session.add(new_vm)
        db.session.commit()

        return f"✅ VM '{vm_name}' with OS '{os_type}' created successfully!"

    except subprocess.CalledProcessError as e:
        return f"❌ Ansible Error: {e}"

@app.route('/view-database')
def view_database():
    vm_list = VMEntry.query.all()
    return render_template('database.html', vms=vm_list)

if __name__ == '__main__':
    app.run(debug=True) 


