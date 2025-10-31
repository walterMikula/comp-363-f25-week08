# Dependencies
from dataclasses import dataclass
import random
from collections import deque, defaultdict

# Size of grid
N = 4
# Length of simulation in time ticks
TOTAL_TICKS = 1_000

# Cardinal direction constants
NORTH = "N"
SOUTH = "S"
EAST = "E"
WEST = "W"

# Directions in clockwise order for easy turning using modular arithmetic
CLOCKWISE = [NORTH, EAST, SOUTH, WEST]

# Turn constants
STRAIGHT = "straight"
LEFT = "left"
RIGHT = "right"

# Turn probabilities [left, straight, right]
TURN_PROBABILITIES = [0.25, 0.50, 0.25]

# Traffic light timing
CYCLE_NS_GREEN = 20
CYCLE_EW_GREEN = 20
CYCLE_TOTAL = CYCLE_NS_GREEN + CYCLE_EW_GREEN

# How many cars car flow through a green light per time tick?
FLOW_PER_TICK = 1

# Link capacity: now many cars in transit are allowed between
# neighboring nodes
LINK_IN_TRANSIT_CAP = 50
# How many cars can wait at a stop light
QUEUE_CAP = 10

# Travel timing
BASE_TRAVEL_T = 6

# Arrival rate: average number of cars arriving per time tick at each edge
ARRIVAL_RATE = 0.33

@dataclass(frozen=True)
class Node:
    i: int  # index of E-W street
    j: int  # index of N-S street


@dataclass
class Car:
    id: int  # unique identifier for the car
    t_enter: int  # time step when the car enters the grid

@dataclass(frozen=True)
class Node:
    i: int  # index of E-W street
    j: int  # index of N-S street


@dataclass
class Car:
    id: int  # unique identifier for the car
    t_enter: int  # time step when the car enters the grid
#Mesoscopic considerations
#We must capture the direction of incoming and outgoing traffic to an intersection, how to process turning, how to handle cars arriving from outside the grid, and how to operate traffic lights.

def outgoing_for(node: Node) -> list[str]:
    """Returns list of (Node, direction) tuples for outgoing links from
    a given node. Most nodes have four outgoing links, but edge nodes
    have fewer. The rules are simple: a node has outgoing to the north,
    for example, if it is not on the northern boundary of the grid, i.e,
    it's i index is greater than 0. Likewise, a node has outgoing
    traffic to the south if its i index is less than N-1, and so on.
    """
    # The directions list to be returned for this node.
    directions = []
    i, j = node.i, node.j  # for easy of use
    if i > 0:
        # northbound traffic leaving to north
        directions.append((Node(i - 1, j), NORTH))
    if j < N - 1:
        # eastbound traffic leaving to east
        directions.append((Node(i, j + 1), EAST))
    if i < N - 1:
        # southbound traffic leaving to south
        directions.append((Node(i + 1, j), SOUTH))
    if j > 0:
        # westbound traffic leaving to west
        directions.append((Node(i, j - 1), WEST))
    return directions


def incoming_for(node: Node) -> list[str]:
    """Returns list of (Node, direction) tuples for incoming links to the node."""
    directions = []
    i, j = node.i, node.j  # for easy of use
    if i < N - 1:
        # northbound traffic arriving from south
        directions.append((Node(i + 1, j), NORTH))
    if j > 0:
        # eastbound traffic arriving from west
        directions.append((Node(i, j - 1), EAST))
    if i > 0:
        # southbound traffic arriving from north
        directions.append((Node(i - 1, j), SOUTH))
    if j < N - 1:
        # westbound traffic arriving from east
        directions.append((Node(i, j + 1), WEST))
    return directions


def turn_direction(approach_direction: str) -> str:
    """Given the direction from which a car is approaching an intersection,
    return the direction the car will turn (left, straight, right)."""
    left, straight, right = TURN_PROBABILITIES
    # Flip a coin to determine turn
    rand = random.random()
    # Determine turn based on given probabilities
    if rand < left:
        turn = LEFT
    elif rand < left+straight:
        turn = STRAIGHT
    else:
        turn = RIGHT
    # Assume we are going straight
    new_direction = approach_direction
    if turn != STRAIGHT:
        # But if direction is not straight, find the index-value of
        # the current approach direction
        approach_idx = CLOCKWISE.index(approach_direction)
        # Assume we are turning left and update the index to counter-clockwise
        # direction by decrementing index and protecting wrap-around using modulo
        new_idx = (approach_idx - 1) % len(CLOCKWISE)
        if turn == RIGHT:
            # If we are turning right, update the index to clockwise direction
            new_idx = (approach_idx + 1) % len(CLOCKWISE)
        # Get the new direction string from the updated index
        new_direction = CLOCKWISE[new_idx]
    # Return the new direction string
    return new_direction


def is_boundary_incoming_link(src: Node, dst: Node) -> bool:
    """Links whose source is on the boundary and destination inside the grid as
    boundary arrival points."""
    si = src.i  # 0 is north boundary, N-1 south
    sj = src.j  # 0 is west boundary, N-1 east
    di = dst.i  # when == si traffic moves N/S, otherwise E/S
    dj = dst.j  # when == sj traffic moves E/W, otherwise N/N
    return (
        (si == 0 and di == si + 1 and sj == dj)  # from outside southbound
        or (si == N - 1 and di == si - 1 and sj == dj)  # from outside northbound
        or (sj == 0 and dj == sj + 1 and si == di)  # from outside eastbound
        or (sj == N - 1 and dj == sj - 1 and si == di)  # from outside westbound
    )


def signal_phase(t: int, node: Node) -> list:
    """Given the current time tick and node, return the list of directions that
    are green for the current signal phase."""
    tt = t % CYCLE_TOTAL
    # Assume east-west is green
    green_axis = [EAST, WEST]
    # Check if we are still in the north-south green phase
    if tt < CYCLE_NS_GREEN:
        # Update the green axis to north-south
        green_axis = [NORTH, SOUTH]
    # Return the direction in which the signal is green
    return green_axis


def add_travel_time(base=BASE_TRAVEL_T):
    """Place holder method so that we can introduce random jitter in
    addition to the base time."""
    return base

# in_transit = dict()  # key -> value: {(u,v) -> Car, remaining time}
# contains the cars currently traveling from node u to node v.
in_transit = dict()

# stopped -- a queue of just cars lining up for one of the
# neighboring nodes.
# key -> value: {(u,v) -> Car lining up at a neighbor light}
stopped = dict()

# Set up the grid of nodes.
nodes = [Node(i, j) for i in range(N) for j in range(N)]

# Initilize the links between nodes
links = []
for u in nodes:
    # For every node in the grid obtain its outgoing links
    for v, direction in outgoing_for(u):
        # v is the destination node from u to v and the
        # direction specified. Add the link u->v
        # in the links list
        links.append((u, v))
        # Start a queue for the cars moving along the link u->v
        in_transit[(u, v)] = deque()
        # Start a queue for the cars stopped at the light for u->v
        stopped[(u, v)] = deque()


def enqueue_departure(src: Node, dst: Node, car: Car) -> bool:
    """Put a car onto the link from the src node to the dst node,
    if space allows.
    """
    # Let's see how many cars are currently on the link src -> dst
    buf = in_transit[(src, dst)]
    success = len(buf) < LINK_IN_TRANSIT_CAP
    if success:
        # There is room; add the car with the default travel time
        buf.append((car, add_travel_time()))
    return success


def pop_to_queue_if_arrived(src: Node, dst: Node) -> int:
    """Cars ending their transit along the (src -> dst)
    link are moved into the downstream stop-light queue"""
    # Get all the cars along the src -> dst link
    buf = in_transit[((src, dst))]
    # Decrease remaining time in the buffer. For some cars the
    # remaining time may reach zero or below. These are the cars
    # we'll move to the downstream queue.
    for k in range(len(buf)):
        car, remaining_time = buf[k]
        buf[k] = (car, remaining_time - 1)
    # Counter for how many cars we move to the downstream queue
    moved = 0
    # Get the downstream queue
    q = stopped[(src, dst)]
    # Any cars whose remaining time is <= 0, should be moved
    # to the downstream stop-light queue. We'll need a tmp
    # queue to stage the cars when there is no room in the
    # downstream queue.
    tmp = deque()
    # Keep looping until we have processed all cars in the buffer
    while buf:
        car, remaining_time = buf.popleft()
        # Check the remaining time of each car in the buffer
        if remaining_time <= 0:
            # Car is done traveling in this link. Move it to
            # the downstream queue if there is room
            if len(q) < QUEUE_CAP:
                q.append(car)
                moved += 1
            else:
                # Car is done traversing the link so set rt=0;
                # However there is no room for it at the stop-light
                # queue, so we have to hold it at the head of the
                # buffer for the next cycle.
                tmp.appendleft((car, 0))
        else:
            # Car still in transit, let's keep it in the buffer
            # with its remaining time in tact.
            tmp.append((car, remaining_time))
        # update the link between src->dst
        in_transit[((src, dst))] = tmp
    # Done
    return moved


def serve_intersection(t: int, node: Node) -> int:
    """Clears queues for approaches that have a green light."""
    green_directions = signal_phase(t, node)
    served = 0  # number of cars moved through the light

    for u, approach_direction in incoming_for(node):

        # skip approaches that are not green
        if approach_direction in green_directions:
            # We are looking at the link from u -> node
            link_key = (u, node)
            # Get the queue for this incoming link
            q = stopped[link_key]
            # Get the number of cars waiting at this light
            moves_attempted = 0
            stop_processing = False  # controls the while loop

            # up to FLOW_PER_TICK vehicles, but stop early if blocked or queue empties
            while moves_attempted < FLOW_PER_TICK and not stop_processing and q:
                car = q[0]

                outgoing_direction = turn_direction(approach_direction)

                # resolve destination node
                i, j = node.i, node.j
                next_node = None
                car_exits = False

                if outgoing_direction == NORTH and i > 0:
                    next_node = Node(i - 1, j)
                elif outgoing_direction == SOUTH and i < N - 1:
                    next_node = Node(i + 1, j)
                elif outgoing_direction == WEST and j > 0:
                    next_node = Node(i, j - 1)
                elif outgoing_direction == EAST and j < N - 1:
                    next_node = Node(i, j + 1)
                else:
                    # car leaves grid
                    car_exits = True

                if car_exits:
                    q.popleft()
                    record_completion(car, t)
                    served += 1
                    moves_attempted += 1
                else:
                    # try to enqueue onto the departing link. enqueue_departure
                    # returns true if successful
                    if enqueue_departure(node, next_node, car):
                        q.popleft()
                        served += 1
                        moves_attempted += 1
                    else:
                        # downstream link is full -> stop serving this approach this tick
                        stop_processing = True

    return served


def record_completion(car: Car, t_now: int) -> None:
    """Records the completion of a car's trip through the grid."""
    global completed, sum_tt
    completed += 1
    sum_tt += t_now - car.t_enter

# Initialization of global statistics

car_id = 0
completed = 0
sum_tt = 0
queue_samples = 0
sum_queue = 0

def simulateDES():
    global car_id, completed, sum_tt, queue_samples, sum_queue
    car_id = 0 
    completed = 0
    sum_tt = 0
    queue_samples = 0
    sum_queue = 0
    for (u, v) in links:
        in_transit[(u, v)].clear()
        stopped[(u, v)].clear()

    for t in range(TOTAL_TICKS):
        for (u, v) in links:
            pop_to_queue_if_arrived(u, v) # move cars that are stopped at lights 

        for node in nodes:
            serve_intersection(t, node) #serve each intersection

        #boundary arrivals
        for (u, v) in links:
            if is_boundary_incoming_link(u, v):
                if random.random() < ARRIVAL_RATE:
                    # A new car arrives at this boundary link
                    car = Car(car_id, t)
                    car_id += 1
                    # Try to enqueue the car onto the link u -> v
                    enqueue_departure(u, v, car)
        total_queue_length = sum(len(stopped[(u, v)]) for (u, v) in links)
        sum_queue = sum_queue + total_queue_length
        queue_samples += 1

    throughput = completed / TOTAL_TICKS if TOTAL_TICKS > 0 else 0.0
    mean_tt = sum_tt / completed if completed > 0 else float ('nan')
    mean_queue = ( sum_queue / max(1, queue_samples))

    print(f"Grid size: {N} x {N}")
    print(f"Number of Ticks: {TOTAL_TICKS}")
    print(f"Traffic Light Cycle: NS Green = {CYCLE_NS_GREEN}, EW Green = {CYCLE_EW_GREEN}")
    print(f"Arrivale rate: {ARRIVAL_RATE}")
    print(f"Trips Completed: {completed}")
    print(f"Throughput: {throughput:.4f}")
    print(f"Mean Travel Time: {None if completed ==0 else round (mean_tt,2)}")
    print(f"Mean Queue Length: {round (mean_queue,2)}")
    print(f"Link Capacity: {LINK_IN_TRANSIT_CAP} / {QUEUE_CAP}")
    print(f"Base Travel Time: {BASE_TRAVEL_T}")
    print(f"flow per green light: {FLOW_PER_TICK}")

if __name__ == "__main__":
    simulateDES()