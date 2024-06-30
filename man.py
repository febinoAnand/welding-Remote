from flask import Flask, request, jsonify, render_template, make_response
from flask_socketio import SocketIO
import serial
import serial.tools.list_ports
import time
from flask_cors import CORS
import webview

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app)

parsed_data = {}
port_name = None
ser = None
baud_rate = 9600

def send_hex(hex_number, ser):
    hex_bytes = bytes.fromhex(hex_number)
    ser.write(hex_bytes)
    print("Sent:", hex_number)

def receive_hex(ser):
    received_bytes = ser.read_all()
    return received_bytes

def parse_received_data(received_bytes, hex_num):
    parsed_data = {}
    try:
        received_hex = received_bytes.hex()
        print("Received hex:", received_hex)

        if hex_num == "0102040605":
            parsed_data['Channel'] = received_bytes[3]
            parsed_data['Sync Address'] = received_bytes[7]
            parsed_data['Destination Address'] = received_bytes[13]
            parsed_data['Source Address'] = received_bytes[15]
            parsed_data['Standby Time'] = received_bytes[11]
            parsed_data['Transmitter Power'] = received_bytes[9]

        elif hex_num == "0102041109":
            parsed_data['Combo First Key'] = received_bytes[5]
            parsed_data['Combo Second Key'] = received_bytes[7]
            parsed_data['Combo Secure'] = received_bytes[3]

        elif hex_num == "0102040F08":
            parsed_data['Low battery v'] = received_bytes[3]

        elif hex_num == "010204000C":
            parsed_data['Device id'] = received_hex[24:28]

        elif hex_num == "010206014E4F4D":
            mode_number_ascii = received_bytes[3:9].decode('ascii')
            parsed_data['Mode no'] = mode_number_ascii

            device_name_ascii = received_bytes[10:12].decode('ascii')
            parsed_data['Device name'] = device_name_ascii

        else:
            print("Hex number not recognized:", hex_num)
            return None

    except Exception as e:
        print("Error parsing received data:", e)

    return parsed_data

@app.route('/')
def welcome_msg():
    return make_response("Welcome")


@app.route('/up', methods=['GET'])
def read_and_emit_data():
    global ser, parsed_data

    try:
        hex_list = ["0102041109", "0102040F08", "0102040605", "010204000C", "010206014E4F4D"]
        parsed_data = {}

        if ser is None or not ser.is_open:
            return jsonify({"error": "Serial port is not open or initialized."})

        for hex_value in hex_list:
            send_hex(hex_value, ser)
            time.sleep(0.5)
            received_data = receive_hex(ser)
            parsed_data.update(parse_received_data(received_data, hex_value))

        socketio.emit('data_update', parsed_data)

        response = jsonify(parsed_data)
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    except serial.SerialException as e:
        return jsonify({"error": str(e)})
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/up', methods=['POST'])
def send_hex_data():
    global ser, parsed_data
    try:
        data = request.json
        print ("Request data-->",data)
        
        if not data:
            return jsonify({'error': 'No JSON data received'}), 400
        
        hex_data = data.get('hex_data')
        print ("Request data-->",hex_data)
        
        if hex_data is None:
            return jsonify({'error': 'Hex data not provided in request'}), 400
        
        send_hex(hex_data, ser)
        
        socketio.emit('data_update', parsed_data)
        print ("parsed data-->                                    :", parsed_data)
        return jsonify({'message': 'Hex data sent successfully'})
    
    except ValueError as ve:
        return jsonify({'error': 'Invalid JSON'}), 400
    except KeyError as ke:
        return jsonify({'error': f'Missing key in JSON: {str(ke)}'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/analog')
def analog():
    return render_template('analog.html')

@app.route('/relay')
def relay():
    return render_template('relay.html')

@app.route('/serial_ports')
def serial_ports():
    print("Request received for serial ports")
    ports = [port.device for port in serial.tools.list_ports.comports()]
    print("Ports found:", ports)
    return jsonify(ports)

port_availability = {}

@app.route('/check_port_availability', methods=['GET'])
def check_port_availability():
    port_name = request.args.get('port_name')
    if port_name in port_availability:
        available = port_availability[port_name]
    else:
        available = False
    return jsonify({'available': available})

@app.route('/connect_port', methods=['GET'])
def connect_port():
    global port_name, ser
    try:
        port_name = request.args.get('port_name')
        
        if port_name is None:
            return jsonify({"error": "Port name is missing in the request."})
     
        available_ports = [port.device for port in serial.tools.list_ports.comports()]
        if port_name not in available_ports:
            print("Port not available:", port_name)
            return jsonify({"error": f"Port not available: {port_name}. Please check the connection."})

        if ser is None or not ser.is_open:
            ser = serial.Serial(port_name, baud_rate)
            print("Successfully connected to port:", port_name)
            return jsonify({"message": f"Successfully connected to port: {port_name}"})
        else:
            print("Port already open:", port_name)
            return jsonify({"message": f"Port already open: {port_name}"})
    except serial.SerialException as e:
        print("Serial port error:", e)
        return jsonify({"error": f"Error: {e}"})
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Error: Something went wrong"})

@app.route('/close_port', methods=['GET'])
def close_port():
    global ser
    try:
        if ser and ser.is_open:
            ser.close()
            print("Serial port closed successfully")
            return jsonify({"message": "Serial port closed successfully"})
        else:
            return jsonify({"message": "Serial port is not open."})
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": "Failed to close serial port"})

@app.route('/check_port_status', methods=['GET'])
def check_port_status():
    port = 5000  
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
    result = sock.connect_ex(('localhost', port))  
    sock.close()  

    if result == 0:
        return jsonify({'status': 'open'})
    else:
        return jsonify({'status': 'closed'})

@socketio.on('connect')
def handle_connect():
    print('connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('disconnected')

if __name__ == "__main__":
    # socketio.run(app, debug=True)
    webview.create_window('Flask App', app)
    webview.start()


