import os
from flask import Flask, render_template, request, jsonify, session
import random
import string

app = Flask(__name__)
app.secret_key = "cfai-exam-seating-2025"

# In-memory data store
# rooms = { room_id: { "name": str, "rows": int, "seats_per_row": int, "seats": { "r1_s1": student_id | None } } }
rooms = {}
# assignments = { student_id: { "room_id": str, "room_name": str, "row": int, "seat": int } }
assignments = {}

ROOM_COUNTER = [0]


def generate_room_id():
    ROOM_COUNTER[0] += 1
    return f"room_{ROOM_COUNTER[0]}"


def is_valid_seat(seat_num):
    """Seats at odd positions (1, 3, 5...) are valid. Even positions are buffers."""
    return seat_num % 2 == 1


def build_seat_map(rows, seats_per_row):
    """Build the initial seat map: odd-numbered seats are valid, even are buffer."""
    seat_map = {}
    for r in range(1, rows + 1):
        for s in range(1, seats_per_row + 1):
            key = f"r{r}_s{s}"
            seat_map[key] = {
                "row": r,
                "seat": s,
                "valid": is_valid_seat(s),
                "occupied_by": None
            }
    return seat_map


def get_all_available_seats():
    """Return list of (room_id, seat_key) tuples for all valid, unoccupied seats."""
    available = []
    for room_id, room in rooms.items():
        for seat_key, seat in room["seats"].items():
            if seat["valid"] and seat["occupied_by"] is None:
                available.append((room_id, seat_key))
    return available


def count_stats():
    total_valid = sum(
        sum(1 for s in room["seats"].values() if s["valid"])
        for room in rooms.values()
    )
    total_occupied = sum(
        sum(1 for s in room["seats"].values() if s["valid"] and s["occupied_by"])
        for room in rooms.values()
    )
    return total_valid, total_occupied


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/api/rooms", methods=["GET"])
def get_rooms():
    result = []
    for room_id, room in rooms.items():
        seats_data = []
        for seat_key, seat in room["seats"].items():
            seats_data.append({
                "key": seat_key,
                "row": seat["row"],
                "seat": seat["seat"],
                "valid": seat["valid"],
                "occupied_by": seat["occupied_by"]
            })
        valid_total = sum(1 for s in room["seats"].values() if s["valid"])
        valid_occupied = sum(1 for s in room["seats"].values() if s["valid"] and s["occupied_by"])
        result.append({
            "id": room_id,
            "name": room["name"],
            "rows": room["rows"],
            "seats_per_row": room["seats_per_row"],
            "seats": seats_data,
            "valid_total": valid_total,
            "valid_occupied": valid_occupied
        })
    return jsonify(result)


@app.route("/api/rooms", methods=["POST"])
def add_room():
    data = request.get_json()
    name = data.get("name", "").strip()
    rows = int(data.get("rows", 0))
    seats_per_row = int(data.get("seats_per_row", 0))

    if not name or rows < 1 or seats_per_row < 1:
        return jsonify({"error": "Invalid room configuration."}), 400

    if rows > 20 or seats_per_row > 20:
        return jsonify({"error": "Maximum 20 rows and 20 seats per row."}), 400

    # Check for duplicate name
    for room in rooms.values():
        if room["name"].lower() == name.lower():
            return jsonify({"error": f'A room named "{name}" already exists.'}), 400

    room_id = generate_room_id()
    rooms[room_id] = {
        "name": name,
        "rows": rows,
        "seats_per_row": seats_per_row,
        "seats": build_seat_map(rows, seats_per_row)
    }
    return jsonify({"success": True, "room_id": room_id, "name": name})


@app.route("/api/rooms/<room_id>", methods=["DELETE"])
def delete_room(room_id):
    if room_id not in rooms:
        return jsonify({"error": "Room not found."}), 404
    # Free up assignments from this room
    to_remove = [sid for sid, info in assignments.items() if info["room_id"] == room_id]
    for sid in to_remove:
        del assignments[sid]
    del rooms[room_id]
    return jsonify({"success": True})


@app.route("/api/assign", methods=["POST"])
def assign_seat():
    data = request.get_json()
    student_id = data.get("student_id", "").strip().upper()

    if not student_id:
        return jsonify({"error": "Please enter your Hall Ticket number."}), 400

    # Already assigned
    if student_id in assignments:
        info = assignments[student_id]
        return jsonify({
            "already_assigned": True,
            "student_id": student_id,
            "room_name": info["room_name"],
            "row": info["row"],
            "seat": info["seat"]
        })

    if not rooms:
        return jsonify({"error": "No examination rooms have been configured yet. Please contact the examination office."}), 400

    available = get_all_available_seats()

    if not available:
        return jsonify({"error": "All seats are currently occupied. Please wait while the examination office adds more rooms."}), 400

    # Random assignment
    chosen_room_id, chosen_seat_key = random.choice(available)
    room = rooms[chosen_room_id]
    seat = room["seats"][chosen_seat_key]

    seat["occupied_by"] = student_id
    assignments[student_id] = {
        "room_id": chosen_room_id,
        "room_name": room["name"],
        "row": seat["row"],
        "seat": seat["seat"]
    }

    return jsonify({
        "success": True,
        "student_id": student_id,
        "room_name": room["name"],
        "row": seat["row"],
        "seat": seat["seat"]
    })


@app.route("/api/stats", methods=["GET"])
def stats():
    total_valid, total_occupied = count_stats()
    return jsonify({
        "rooms": len(rooms),
        "total_seats": total_valid,
        "occupied": total_occupied,
        "available": total_valid - total_occupied,
        "total_assignments": len(assignments)
    })


if __name__ == "__main__":
app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))