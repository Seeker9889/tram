from kivy.app import App
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.properties import NumericProperty, ReferenceListProperty
from kivy.utils import rgba
from kivy.clock import Clock
from random import choice, randint
from enum import Enum
import time
import numpy as num

Window.size = (1300, 100)

class Colors(Enum):
    EMPTY_TRAM = "#E2E2E2"
    EMPTY_TUBE = "#2D2D2D"
    PUSH_INDICATOR = "#FFFFFF"
    PURPLE_RIDER = "#7A68D6"
    GREEN_RIDER = "#0C9038"
    GOLD_RIDER = "#D6C260"
    BLUE_RIDER = "#7CE8D6"

#https://davidmathlogic.com/colorblind/#%23D81B60-%231E88E5-%23FFC107-%23004D40 and https://personal.sron.nl/~pault/ for colorblind choices

class Direction(Enum):
    EAST = -1
    WEST = 1

class Station:
    def __init__(self, west_pos, dropoff_rider):
        self.west_pos = west_pos
        self.dropoff_rider = dropoff_rider
    west_pos = 0
    dropoff_rider = Colors.GREEN_RIDER

fixed_line_len = 150
starting_vel = 0.6
starting_riders = [Colors.EMPTY_TRAM, Colors.EMPTY_TRAM, Colors.EMPTY_TRAM, Colors.EMPTY_TRAM]
starting_rider_pool = [Colors.GREEN_RIDER, Colors.PURPLE_RIDER, Colors.GOLD_RIDER, Colors.BLUE_RIDER]

clock_period = 1.0 / 60.0
frame_rate = 1.0 / 60.0

move_west_keys = ['a', 's', 'd', 'f', 'q', 'w', 'e', 'r', 'z', 'x', 'c', 'v']
move_east_keys = ['l', 'k', 'j', 'h', 'p', 'o', 'i', 'u', ',', 'm', 'n', 'b',]

move_delta = 0.4
max_speed = 2.0
friction = 0.005
rider_dropoff_max_vel = 0.02

class LineState():
    def __init__(self, line_len, riders, rider_pool):
        self.line_len = line_len
        self.car_riders = riders
        self.rider_pool = rider_pool
        self.rider_len = num.floor(self.car_len / len(self.car_riders)).astype(int)
    line_len = 0
    car_west_pos = line_len
    car_len = 12
    car_riders = [Colors.EMPTY_TRAM, Colors.EMPTY_TRAM, Colors.EMPTY_TRAM, Colors.EMPTY_TRAM]
    car_frame_vel = Direction.EAST.value * starting_vel
    station_len = 14
    rider_len = 0
    rider_pool = []
    stations = []

    def car_rider_poses(self):
        car_rider_poses = []
        car_west_atom = round(self.car_west_pos)
        for n, rider in enumerate(self.car_riders):
            rider_west = car_west_atom - (n * self.rider_len)
            for rider_atom in range(rider_west-self.rider_len+1, rider_west+1):
                car_rider_poses.append( (rider_atom, rider) )
        return car_rider_poses

    def car_color_poses(self):
        car_rider_poses = self.car_rider_poses()

        for n, rider_pos in enumerate(car_rider_poses):
            if rider_pos[0] >= self.line_len:
                car_rider_poses[n] = (rider_pos[0] - self.line_len, rider_pos[1])
            elif rider_pos[0] < 0:
                car_rider_poses[n] = (rider_pos[0] + self.line_len, rider_pos[1])
        
        return dict(car_rider_poses)

    def station_poses(self):
        station_poses = []
        for s in self.stations:
            station_poses.append((range(s.west_pos-self.station_len+1, s.west_pos+1), s.dropoff_rider))
        return station_poses

    def station_color_poses(self):
        station_color_poses = dict()
        for s in self.station_poses():
            for pos in s[0]:
                station_color_poses[pos] = s[1]
        return station_color_poses

    def valid_station_west_poses(self):
        buffer = max(self.station_len, self.car_len)
        invalid_poses = []
        # Car positions; add one to account for range(inclusive, exclusive)
        #working_car_west_pos = round(self.car_west_pos)+1
        #invalid_poses.extend(range(working_car_west_pos-self.car_len-buffer, working_car_west_pos+buffer))
        
        # Existing station positions
        for s in self.stations:
            invalid_poses.extend(range(s.west_pos+1-buffer*2, s.west_pos+1+buffer))
        
        valid_west_poses = list(x for x in range(buffer, self.line_len-buffer) if x not in invalid_poses)
        return valid_west_poses

    def direction(self):
        return (Direction.WEST, Direction.EAST) [self.car_frame_vel >= 0]

class LineGame(Widget):

    line_state = None
    last_frame_time = 0

    def __init__(self, **kwargs):
        super(LineGame, self).__init__(**kwargs)
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down = self._on_keyboard_down)

        self.line_state = LineState(fixed_line_len, starting_riders, starting_rider_pool)
        starting_color = rgba(Colors.EMPTY_TUBE.value)
        self.line_state = self.add_rider(self.line_state, [], 35)
        for n in range(0, self.line_state.line_len):
            newAtom = Atom()
            newAtom.color = starting_color
            self.ids.g_box.add_widget(newAtom)

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None
    
    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        if keycode[1] in move_west_keys and self.line_state.car_frame_vel < max_speed * Direction.WEST.value:
            self.line_state.car_frame_vel = self.line_state.car_frame_vel + ( move_delta * Direction.WEST.value )
        if keycode[1] in move_east_keys and self.line_state.car_frame_vel > max_speed * Direction.EAST.value:
            self.line_state.car_frame_vel = self.line_state.car_frame_vel + ( move_delta * Direction.EAST.value )
        return True

    def update(self, dt):

        self.line_state = self.process_changes(self.line_state)

        self.draw(self.cast_to_atoms(self.line_state))

        pass

    def add_station(self, line_state: LineState, color, override_station_west_pos = None):
        valid_station_west_poses = line_state.valid_station_west_poses()
        if override_station_west_pos != None:
            station_west_pos = override_station_west_pos
        elif len(valid_station_west_poses) > 0:
            station_west_pos = choice(valid_station_west_poses)
        else:
            line_state.car_riders[:] = [Colors.EMPTY_TRAM if rider==color else rider for rider in line_state.car_riders]
            line_state = self.add_rider(line_state, [color])

        station = Station(station_west_pos, color)

        line_state.stations.append(station)
        return line_state

    def add_rider(self, line_state: LineState, riders_to_exclude, override_station_west_pos = None):
        if Colors.EMPTY_TRAM not in line_state.car_riders:
            return line_state
        empty_seat_index = line_state.car_riders.index(Colors.EMPTY_TRAM)
        new_rider = choice([rider for rider in line_state.rider_pool if rider not in riders_to_exclude])
        line_state.car_riders[empty_seat_index] = new_rider

        if new_rider not in [station.dropoff_rider for station in line_state.stations]:
            line_state = self.add_station(line_state, new_rider, override_station_west_pos)

        return line_state

    def add_friction(self, line_state: LineState):
        if abs(line_state.car_frame_vel) > friction:
            if num.sign(line_state.car_frame_vel) == Direction.WEST.value:
                line_state.car_frame_vel = line_state.car_frame_vel - friction
            elif num.sign(line_state.car_frame_vel) == Direction.EAST.value:
                line_state.car_frame_vel = line_state.car_frame_vel + friction
        else:
            line_state.car_frame_vel = 0

        return line_state

    def exchange_riders(self, line_state: LineState):
        if abs(line_state.car_frame_vel) < rider_dropoff_max_vel:
            station_color_poses = line_state.station_color_poses()
            car_color_poses = line_state.car_color_poses()
            station_car_inter_color = set([station_color_poses[pos] for pos in station_color_poses if pos in car_color_poses and station_color_poses[pos] in line_state.car_riders])

            for color in station_car_inter_color:
                line_state.car_riders[:] = [Colors.EMPTY_TRAM if rider==color else rider for rider in line_state.car_riders]
                # Randomly attempt to add 1-4 riders
                extra_rider_roll = max(1, randint(1,7) - 3)
                for x in range(extra_rider_roll):
                    line_state = self.add_rider(self.line_state, [color])
                
        return line_state

    def process_changes(self, line_state: LineState):
        line_state = self.add_friction(line_state)

        curr_time_in_sec = time.time_ns() / 1000000000
        delta_time_in_frames = 1
        # Get difference in seconds between this frame and previous frame
        # frame_rate is in second fraction; invert and multiply by delta time to get actual frame time
        if (self.last_frame_time > 0):
            delta_time = curr_time_in_sec - self.last_frame_time
            delta_time_in_frames = round(delta_time * (1/frame_rate))
        self.last_frame_time = curr_time_in_sec
            
        car_pos_delta = line_state.car_frame_vel * delta_time_in_frames

        line_state.car_west_pos += car_pos_delta
        if line_state.car_west_pos < 0:
            line_state.car_west_pos = line_state.line_len-1
        elif line_state.car_west_pos > line_state.line_len:
            line_state.car_west_pos = 0

        line_state = self.exchange_riders(line_state)

        return line_state

    def cast_to_atoms(self, current_state: LineState):
        colors = []

        car_color_poses = current_state.car_color_poses()
        
        station_color_poses = current_state.station_color_poses()

        for n in range(0,current_state.line_len):
            if n in car_color_poses:
                colors.append(rgba(car_color_poses[n].value))
            elif n in station_color_poses:
                colors.append(rgba(station_color_poses[n].value))
            else:
                colors.append(rgba(Colors.EMPTY_TUBE.value))
        return colors

    def draw(self, allColors):
        atoms = self.ids.g_box.children
        for n, atom in enumerate(atoms):
            atom.color = allColors[n]
        pass

class LineApp(App):
    def build(self):
        self.icon = 'icon.png'
        game = LineGame()
        Clock.schedule_interval(game.update, clock_period)
        return game


class Atom(Widget):
    color_r = NumericProperty(1)
    color_g = NumericProperty(1)
    color_b = NumericProperty(1)
    color_a = NumericProperty(1)
    color = ReferenceListProperty(color_r, color_g, color_b, color_a)

if __name__ == '__main__':
    LineApp().run()