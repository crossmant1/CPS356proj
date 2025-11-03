"""
======================================
CPS 356: Operating Systems - Project 1
======================================

THREADING ARCHITECTURE:
- Main thread: Handles pygame event loop and rendering
- Car threads: Each car runs in its own thread for concurrent movement
- Timer thread: Tracks race elapsed time
- All threads synchronized using threading primitives

SYNCHRONIZATION MECHANISMS:
- threading.Lock (Mutex): Protects shared game state (car positions, winner)
- threading.Event: Used for pause/resume functionality
- Atomic operations: Flag checks for race completion

BONUS FEATURES IMPLEMENTED:
1. Obstacles: Random obstacles on track that slow down cars
2. Power-ups: Speed boost and shield/invincibility
3. Multiplayer: Player can control one car with arrow keys

RACE CONDITIONS PREVENTED:
- Grid state updates protected by mutex
- Winner detection uses lock to ensure only one winner
- Collision detection synchronized with position updates
"""

# Nick wrote this

import pygame
import threading
import time
import random
import sys

# ============================================================================
# GLOBAL CONSTANTS - Game Configuration
# ============================================================================

# Window dimensions
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 600

# Track configuration
TRACK_LANES = 4
LANE_HEIGHT = WINDOW_HEIGHT // TRACK_LANES
START_X = 50
FINISH_LINE_X = WINDOW_WIDTH - 100

# Game object sizes
CAR_WIDTH = 40
CAR_HEIGHT = 25
OBSTACLE_SIZE = 30
POWERUP_SIZE = 25

# Game mechanics
NUM_CARS = 4
NUM_OBSTACLES = 8
NUM_POWERUPS = 6
BASE_SPEED = 2
SPEED_VARIANCE = 1

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 100, 255)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
GRAY = (128, 128, 128)
DARK_GREEN = (0, 128, 0)
GOLD = (255, 215, 0)

# Car colors
CAR_COLORS = [RED, GREEN, BLUE, YELLOW]


# ============================================================================
# CAR CLASS by Nicholas Keane
# Represents individual race car with its own thread
# ============================================================================

# Nick wrote this
class Car:
    """
    Car object that runs in its own thread.

    Thread Safety:
    - Position updates protected by game state lock
    - Movement controlled by pause event
    - Thread-safe flag checking for race completion
    """

    def __init__(self, car_id, lane, color, is_player=False):
        self.id = car_id
        self.lane = lane
        self.x = START_X
        self.y = lane * LANE_HEIGHT + (LANE_HEIGHT - CAR_HEIGHT) // 2
        self.color = color
        self.base_speed = BASE_SPEED + random.uniform(-SPEED_VARIANCE, SPEED_VARIANCE)
        self.current_speed = self.base_speed
        self.finished = False
        self.finish_time = None
        self.is_player = is_player

        # Bonus features: Power-ups
        self.hasSpeedBoost = False
        self.speedBoostTimer = 0
        self.hasShield = False
        self.shieldTimer = 0

        # Thread reference
        self.thread = None

    def get_rect(self):
        """Returns pygame Rect for collision detection"""
        return pygame.Rect(self.x, self.y, CAR_WIDTH, CAR_HEIGHT)

    # Jared's code
    def powerUpType(self, powerUpType):

        """
        Apply power-up effect to car depending on the powerup.
        CRITICAL SECTION: Called from car thread and modifies car state. It's rotected by caller's lock

        """

        if powerUpType == "speed":
            self.hasSpeedBoost = True
            self.speedBoostTimer = 1.5  # 1.5 seconds
            self.current_speed = self.base_speed * 2

        elif powerUpType == "shield":
            self.hasShield = True
            self.shieldTimer = 3.0  # 3 seconds

    #Jared's code
    def updatePowerUps(self, deltaTime):

        """
        Update the time for the power-up timers.
        THREAD SAFETY: Called from car's own thread. No lock needed as no other threads modify these values.

        """

        if self.hasSpeedBoost:
            self.speedBoostTimer -= deltaTime

            if self.speedBoostTimer <= 0:
                self.hasSpeedBoost = False
                self.current_speed = self.base_speed

        if self.hasShield:
            self.shieldTimer -= deltaTime

            if self.shieldTimer <= 0:
                self.hasShield = False


# ============================================================================
# OBSTACLE CLASS by Jared Milelr
# Static obstacles that slow down cars on collision
# ============================================================================

#Jared's code
class Obstacle:

    """Obstacles will slow down cars when the obstacle is hit unless they have shield"""

    def __init__(self, x, lane):
        self.x = x
        self.lane = lane
        self.y = lane * LANE_HEIGHT + (LANE_HEIGHT - OBSTACLE_SIZE) // 2
        self.active = True

    def getRectangle(self):
        return pygame.Rect(self.x, self.y, OBSTACLE_SIZE, OBSTACLE_SIZE)


# ============================================================================
# POWERUP CLASS by Jared Miller
# Collectible items that give cars special benefits
# ============================================================================

#Jared's code
class PowerUp:
    """Collectible item that can be a speed boost or shield"""

    def __init__(self, x, lane, powerUpType):
        self.x = x
        self.lane = lane
        self.y = lane * LANE_HEIGHT + (LANE_HEIGHT - POWERUP_SIZE) // 2
        self.type = powerUpType  # "speed" or "shield"
        self.active = True
        self.rotation = 0  # For animation

    def getRectangle(self):
        return pygame.Rect(self.x, self.y, POWERUP_SIZE, POWERUP_SIZE)


# ============================================================================
# GAME CLASS Rendering: David Weaver, 
# Main game controller managing all threads and synchronization
# ============================================================================

class RacingGame:
    """
    Main game class coordinating all threads and managing shared state.

    SYNCHRONIZATION STRATEGY:
    - state_lock: Protects all shared game state (mutex)
    - pause_event: Controls thread execution (event signaling)
    - race_active: Atomic flag for race status
    - winner_declared: Atomic flag to prevent multiple winners
    """

    def __init__(self):
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Multi-threaded Racing Game - CPS 356")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        # ====================================================================
        # SYNCHRONIZATION PRIMITIVES
        # ====================================================================

        # Mutex for protecting shared state
        self.state_lock = threading.Lock()

        # Event for pause/resume functionality
        self.pause_event = threading.Event()
        self.pause_event.set()  # Initially not paused

        # Atomic flags
        self.race_active = False
        self.winner_declared = False

        # ====================================================================
        # SHARED GAME STATE (Protected by state_lock)
        # ====================================================================

        self.cars = []
        self.obstacles = []
        self.powerups = []
        self.winner = None
        self.race_start_time = None
        self.race_time = 0
        self.game_state = "menu"  # menu, racing, paused, finished

        self.initialize_game_objects()

    def initialize_game_objects(self):
        """
        Initialize all game objects: cars, obstacles, powerups.

        THREAD SAFETY: Called only from main thread during setup
        No lock needed as no other threads are running yet
        """

        # Create cars (first car is player-controlled)
        self.cars = []
        for i in range(NUM_CARS):
            is_player = (i == 0)
            car = Car(i, i, CAR_COLORS[i], is_player)
            self.cars.append(car)

        # Create obstacles at random positions
        self.obstacles = []
        for i in range(NUM_OBSTACLES):
            x = random.randint(START_X + 150, FINISH_LINE_X - 150)
            lane = random.randint(0, TRACK_LANES - 1)
            self.obstacles.append(Obstacle(x, lane))

        # Create power-ups at random positions
        self.powerups = []
        for i in range(NUM_POWERUPS):
            x = random.randint(START_X + 200, FINISH_LINE_X - 200)
            lane = random.randint(0, TRACK_LANES - 1)
            powerUpType = random.choice(["speed", "shield"])
            self.powerups.append(PowerUp(x, lane, powerUpType))

    def reset_game(self):
        """
        Reset game to initial state.

        CRITICAL SECTION: Must ensure all threads are stopped before reset
        """

        # Stop all car threads
        self.race_active = False
        self.pause_event.set()  # Wake up any paused threads so they can exit

        # Wait for all threads to finish
        for car in self.cars:
            if car.thread and car.thread.is_alive():
                car.thread.join(timeout=1.0)

        # Reset state
        with self.state_lock:
            self.winner_declared = False
            self.winner = None
            self.race_start_time = None
            self.race_time = 0
            self.initialize_game_objects()

        self.game_state = "menu"

    def start_race(self):
        """
        Start the race by creating and starting all car threads.

        THREAD CREATION: Spawns one thread per car
        Each thread runs the car_movement_thread function
        """

        self.game_state = "racing"
        self.race_active = True
        self.winner_declared = False
        self.race_start_time = time.time()
        self.pause_event.set()

        # Create and start a thread for each car
        for car in self.cars:
            if not car.is_player:  # AI-controlled cars
                car.thread = threading.Thread(
                    target=self.car_movement_thread,
                    args=(car,),
                    daemon=True
                )
                car.thread.start()

    def car_movement_thread(self, car):
        """
        Thread function for autonomous car movement.

        THREAD FUNCTION: Runs in separate thread for each AI car

        SYNCHRONIZATION:
        - Checks pause_event before each movement
        - Uses state_lock when updating position
        - Checks race_active flag to know when to exit

        RACE CONDITIONS PREVENTED:
        - Position updates are atomic (protected by lock)
        - Collision detection synchronized with movement
        - Winner detection uses lock and atomic flag
        """

        last_update = time.time()

        while self.race_active and not car.finished:
            # Wait if game is paused
            self.pause_event.wait()

            # Calculate delta time for frame-independent movement
            current_time = time.time()
            dt = current_time - last_update
            last_update = current_time

            # Update power-up timers (no lock needed, car-local data)
            car.updatePowerUps(dt)

            # Random speed variation to simulate realistic racing
            speed_multiplier = random.uniform(0.8, 1.2)
            move_distance = car.current_speed * speed_multiplier

            # CRITICAL SECTION: Update car position and check collisions
            with self.state_lock:
                if not self.race_active:
                    break

                # Move car forward
                car.x += move_distance

                # Check collision with obstacles
                car_rect = car.get_rect()
                for obstacle in self.obstacles:
                    if obstacle.active and car_rect.colliderect(obstacle.getRectangle()):
                        if not car.hasShield:
                            # Slow down car on collision
                            car.x -= move_distance * 0.5
                        obstacle.active = False  # Remove obstacle after hit

                # Check collision with power-ups
                for powerup in self.powerups:
                    if powerup.active and car_rect.colliderect(powerup.getRectangle()):
                        car.powerUpType(powerup.type)
                        powerup.active = False

                # Check if car reached finish line
                if car.x >= FINISH_LINE_X and not car.finished:
                    car.finished = True
                    car.finish_time = time.time() - self.race_start_time

                    # CRITICAL SECTION: Winner declaration (atomic operation)
                    if not self.winner_declared:
                        self.winner_declared = True
                        self.winner = car
                        self.game_state = "finished"

            # Sleep to control thread execution rate (simulate thread scheduling)
            time.sleep(0.016)  # Approximately 60 FPS

    def handle_player_input(self):
        """
        Handle player keyboard input for car control.

        THREAD SAFETY: Called from main thread only
        Uses lock when modifying car position
        """

        if self.game_state != "racing" or not self.race_active:
            return

        keys = pygame.key.get_pressed()
        player_car = self.cars[0]

        if player_car.finished:
            return

        # Calculate delta time
        dt = self.clock.get_time() / 1000.0
        player_car.updatePowerUps(dt)

        # CRITICAL SECTION: Update player car position
        with self.state_lock:
            # Forward movement
            if keys[pygame.K_RIGHT]:
                move_distance = player_car.current_speed * 1.5
                player_car.x += move_distance

                # Check collisions
                car_rect = player_car.get_rect()
                for obstacle in self.obstacles:
                    if obstacle.active and car_rect.colliderect(obstacle.getRectangle()):
                        if not player_car.hasShield:
                            player_car.x -= move_distance * 0.5
                        obstacle.active = False

                for powerup in self.powerups:
                    if powerup.active and car_rect.colliderect(powerup.getRectangle()):
                        player_car.powerUpType(powerup.type)
                        powerup.active = False

                # Check finish line
                if player_car.x >= FINISH_LINE_X and not player_car.finished:
                    player_car.finished = True
                    player_car.finish_time = time.time() - self.race_start_time

                    if not self.winner_declared:
                        self.winner_declared = True
                        self.winner = player_car
                        self.game_state = "finished"

            # Lane switching
            if keys[pygame.K_UP] and player_car.lane > 0:
                player_car.lane -= 1
                player_car.y = player_car.lane * LANE_HEIGHT + (LANE_HEIGHT - CAR_HEIGHT) // 2
                time.sleep(0.2)  # Prevent rapid lane switching

            if keys[pygame.K_DOWN] and player_car.lane < TRACK_LANES - 1:
                player_car.lane += 1
                player_car.y = player_car.lane * LANE_HEIGHT + (LANE_HEIGHT - CAR_HEIGHT) // 2
                time.sleep(0.2)
    
    def toggle_pause(self):
        """
        Pause/Resume race using threading.Event.

        SYNCHRONIZATION: Event-based pause mechanism
        - clear() blocks all waiting threads
        - set() releases all waiting threads
        """

        if self.game_state == "racing":
            if self.pause_event.is_set():
                self.pause_event.clear()  # Pause
                self.game_state = "paused"
            else:
                self.pause_event.set()  # Resume
                self.game_state = "racing"
    # David's code
    def draw_track(self):
        # Background
        self.screen.fill(GRAY)

        # Lane dividers
        for i in range(1, TRACK_LANES):
            y = i * LANE_HEIGHT
            pygame.draw.line(self.screen, WHITE, (0, y), (WINDOW_WIDTH, y), 2)

        # Start line
        pygame.draw.line(self.screen, GREEN, (START_X, 0), (START_X, WINDOW_HEIGHT), 4)

        # Finish line (checkered pattern)
        for i in range(0, WINDOW_HEIGHT, 20):
            color = WHITE if (i // 20) % 2 == 0 else BLACK
            pygame.draw.rect(self.screen, color, (FINISH_LINE_X, i, 20, 20))
    # David's code
    def draw_game_objects(self):
        with self.state_lock:
            # Draw obstacles
            for obstacle in self.obstacles:
                if obstacle.active:
                    pygame.draw.rect(self.screen, ORANGE,
                                     (obstacle.x, obstacle.y, OBSTACLE_SIZE, OBSTACLE_SIZE))
                    pygame.draw.rect(self.screen, BLACK,
                                     (obstacle.x, obstacle.y, OBSTACLE_SIZE, OBSTACLE_SIZE), 2)

            # Draw power-ups
            for powerup in self.powerups:
                if powerup.active:
                    color = GOLD if powerup.type == "speed" else PURPLE
                    pygame.draw.circle(self.screen, color,
                                       (int(powerup.x + POWERUP_SIZE // 2),
                                        int(powerup.y + POWERUP_SIZE // 2)),
                                       POWERUP_SIZE // 2)

                    # Draw icon
                    if powerup.type == "speed":
                        # Lightning bolt
                        points = [(powerup.x + 12, powerup.y + 5),
                                  (powerup.x + 15, powerup.y + 12),
                                  (powerup.x + 13, powerup.y + 12),
                                  (powerup.x + 16, powerup.y + 20),
                                  (powerup.x + 10, powerup.y + 13),
                                  (powerup.x + 12, powerup.y + 13)]
                        pygame.draw.polygon(self.screen, WHITE, points)
                    else:
                        # Shield
                        pygame.draw.circle(self.screen, WHITE,
                                           (int(powerup.x + POWERUP_SIZE // 2),
                                            int(powerup.y + POWERUP_SIZE // 2)),
                                           POWERUP_SIZE // 3, 2)

            # Draw cars
            for car in self.cars:
                # Car body
                pygame.draw.rect(self.screen, car.color,
                                 (int(car.x), int(car.y), CAR_WIDTH, CAR_HEIGHT))
                pygame.draw.rect(self.screen, BLACK,
                                 (int(car.x), int(car.y), CAR_WIDTH, CAR_HEIGHT), 2)

                # Draw power-up indicators
                if car.hasSpeedBoost:
                    pygame.draw.circle(self.screen, GOLD,
                                       (int(car.x + CAR_WIDTH - 5), int(car.y + 5)), 5)
                if car.hasShield:
                    pygame.draw.circle(self.screen, PURPLE,
                                       (int(car.x + CAR_WIDTH // 2), int(car.y + CAR_HEIGHT // 2)),
                                       CAR_HEIGHT, 2)

                # Player indicator
                if car.is_player:
                    text = self.small_font.render("YOU", True, WHITE)
                    self.screen.blit(text, (int(car.x), int(car.y - 20)))
    # David's code 
    def draw_ui(self):
        # Race timer
        if self.race_start_time and self.game_state in ["racing", "paused"]:
            elapsed = time.time() - self.race_start_time
            timer_text = self.small_font.render(f"Time: {elapsed:.2f}s", True, WHITE)
            self.screen.blit(timer_text, (10, 10))

        # Game state
        if self.game_state == "menu":
            title = self.font.render("Multi-threaded Racing Game", True, WHITE)
            self.screen.blit(title, (WINDOW_WIDTH // 2 - 250, WINDOW_HEIGHT // 2 - 100))

            instructions = [
                "SPACE - Start Race",
                "Arrow Keys - Control Red Car (Player)",
                "P - Pause/Resume",
                "R - Reset",
                "",
                "Power-ups: Gold=Speed, Purple=Shield",
                "Orange Squares = Obstacles"
            ]

            y_offset = WINDOW_HEIGHT // 2
            for instruction in instructions:
                text = self.small_font.render(instruction, True, WHITE)
                self.screen.blit(text, (WINDOW_WIDTH // 2 - 200, y_offset))
                y_offset += 30

        elif self.game_state == "paused":
            text = self.font.render("PAUSED", True, YELLOW)
            self.screen.blit(text, (WINDOW_WIDTH // 2 - 80, WINDOW_HEIGHT // 2))

        elif self.game_state == "finished":
            with self.state_lock:
                if self.winner:
                    winner_text = f"Car {self.winner.id + 1} WINS!"
                    if self.winner.is_player:
                        winner_text = "YOU WIN!"

                    text = self.font.render(winner_text, True, GOLD)
                    self.screen.blit(text, (WINDOW_WIDTH // 2 - 120, WINDOW_HEIGHT // 2 - 50))

                    time_text = self.small_font.render(
                        f"Time: {self.winner.finish_time:.2f}s", True, WHITE)
                    self.screen.blit(time_text, (WINDOW_WIDTH // 2 - 80, WINDOW_HEIGHT // 2))

                    restart = self.small_font.render("Press R to restart", True, WHITE)
                    self.screen.blit(restart, (WINDOW_WIDTH // 2 - 100, WINDOW_HEIGHT // 2 + 40))

    def run(self):
        running = True

        while running:
            # Event handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE and self.game_state == "menu":
                        self.start_race()

                    elif event.key == pygame.K_p:
                        self.toggle_pause()

                    elif event.key == pygame.K_r:
                        self.reset_game()

            # Handle player input
            self.handle_player_input()

            # Rendering: David
            self.draw_track()
            self.draw_game_objects()
            self.draw_ui()

            pygame.display.flip()
            self.clock.tick(60)  # 60 FPS

        # Cleanup: Stop all threads before exit
        self.race_active = False
        self.pause_event.set()

        for car in self.cars:
            if car.thread and car.thread.is_alive():
                car.thread.join(timeout=1.0)

        pygame.quit()
        sys.exit()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    game = RacingGame()
    game.run()
