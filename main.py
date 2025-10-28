"""
CPS 356: Operating Systems - Project 1
Multi-threaded Racing Game
Demonstrates multi-threading with synchronization mechanisms
"""

import tkinter as tk
from threading import Thread, Lock
import random
import time

class RacingGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-threaded Racing Game")
        
        # Game configuration
        self.num_cars = 2
        self.track_length = 700  # pixels
        self.car_size = 40
        self.finish_line_x = self.track_length - 50
        
        # Shared state (protected by locks)
        self.car_positions = [0, 0]  # Current x-position of each car
        self.position_lock = Lock()  # Mutex to protect position updates
        self.race_active = False
        self.winner = None
        self.winner_lock = Lock()  # Mutex to protect winner detection
        
        # Thread references
        self.car_threads = []
        
        # Setup GUI
        self.setup_gui()
        
    def setup_gui(self):
        """Create the user interface"""
        # Control frame
        control_frame = tk.Frame(self.root)
        control_frame.pack(pady=10)
        
        self.start_button = tk.Button(
            control_frame, 
            text="Start Race", 
            command=self.start_race,
            font=("Arial", 14),
            bg="green",
            fg="white",
            padx=20
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(
            control_frame,
            text="Stop Race",
            command=self.stop_race,
            font=("Arial", 14),
            bg="red",
            fg="white",
            padx=20,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        self.reset_button = tk.Button(
            control_frame,
            text="Reset",
            command=self.reset_race,
            font=("Arial", 14),
            padx=20
        )
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Press Start to begin the race!",
            font=("Arial", 16, "bold"),
            fg="blue"
        )
        self.status_label.pack(pady=10)
        
        # Canvas for drawing the race track
        self.canvas = tk.Canvas(
            self.root,
            width=self.track_length + 100,
            height=200,
            bg="lightgray"
        )
        self.canvas.pack(pady=20)
        
        # Draw initial track
        self.draw_track()
        
    def draw_track(self):
        """Draw the racing track, finish line, and cars"""
        self.canvas.delete("all")
        
        # Draw lanes
        lane_height = 60
        for i in range(self.num_cars):
            y = 50 + i * lane_height
            # Lane background
            self.canvas.create_rectangle(
                50, y, self.track_length, y + 40,
                fill="white", outline="black", width=2
            )
            # Lane divider
            if i > 0:
                self.canvas.create_line(
                    50, y, self.track_length, y,
                    fill="gray", dash=(5, 5)
                )
        
        # Draw starting line
        self.canvas.create_line(
            50, 40, 50, 40 + self.num_cars * 60,
            fill="green", width=5
        )
        self.canvas.create_text(
            50, 25, text="START", font=("Arial", 12, "bold"), fill="green"
        )
        
        # Draw finish line
        finish_x = self.finish_line_x
        self.canvas.create_line(
            finish_x, 40, finish_x, 40 + self.num_cars * 60,
            fill="red", width=5
        )
        self.canvas.create_text(
            finish_x, 25, text="FINISH", font=("Arial", 12, "bold"), fill="red"
        )
        
        # Draw cars
        self.draw_cars()
        
    def draw_cars(self):
        """Draw cars at their current positions"""
        colors = ["blue", "red"]
        lane_height = 60
        
        for i in range(self.num_cars):
            # Get position with thread safety
            with self.position_lock:
                x_pos = self.car_positions[i]
            
            y = 50 + i * lane_height + 20  # Center of lane
            
            # Draw car as a rectangle
            self.canvas.create_rectangle(
                50 + x_pos, y - 15,
                50 + x_pos + self.car_size, y + 15,
                fill=colors[i], outline="black", width=2,
                tags=f"car{i}"
            )
            
            # Car label
            self.canvas.create_text(
                50 + x_pos + self.car_size // 2, y,
                text=f"Car {i+1}",
                font=("Arial", 10, "bold"),
                fill="white",
                tags=f"car{i}"
            )
    
    def car_thread_function(self, car_id):
        """
        Thread function for car movement
        Each car runs this function in its own thread
        """
        while True:
            # Check if race should stop
            if not self.race_active:
                break
            
            # Check if there's already a winner
            with self.winner_lock:
                if self.winner is not None:
                    break
            
            # Random speed variation (simulate different speeds)
            # Sleep between 0.05 and 0.15 seconds
            sleep_time = random.uniform(0.05, 0.15)
            time.sleep(sleep_time)
            
            # Random movement amount (1-5 pixels)
            movement = random.randint(1, 5)
            
            # Update position with mutual exclusion (critical section)
            with self.position_lock:
                self.car_positions[car_id] += movement
                current_pos = self.car_positions[car_id]
            
            # Check if car reached finish line
            if current_pos >= self.finish_line_x - 50:
                # Use lock to ensure only one winner is declared
                with self.winner_lock:
                    if self.winner is None:
                        self.winner = car_id
                        # Update GUI from main thread
                        self.root.after(0, self.declare_winner, car_id)
                break
            
            # Request GUI update from main thread (thread-safe)
            self.root.after(0, self.draw_cars)
    
    def start_race(self):
        """Start the race by creating and starting car threads"""
        if self.race_active:
            return
        
        self.race_active = True
        self.winner = None
        self.status_label.config(text="Race in progress...", fg="blue")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Create and start threads for each car
        self.car_threads = []
        for i in range(self.num_cars):
            thread = Thread(target=self.car_thread_function, args=(i,))
            thread.daemon = True  # Thread will terminate when main program exits
            thread.start()
            self.car_threads.append(thread)
    
    def stop_race(self):
        """Stop the race and terminate threads"""
        self.race_active = False
        self.status_label.config(text="Race stopped!", fg="orange")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        # Wait for all threads to finish
        for thread in self.car_threads:
            if thread.is_alive():
                thread.join(timeout=1.0)
    
    def reset_race(self):
        """Reset the race to initial state"""
        # Stop race if active
        if self.race_active:
            self.stop_race()
        
        # Reset positions
        with self.position_lock:
            self.car_positions = [0] * self.num_cars
        
        # Reset winner
        with self.winner_lock:
            self.winner = None
        
        # Reset GUI
        self.status_label.config(text="Press Start to begin the race!", fg="blue")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.draw_track()
    
    def declare_winner(self, car_id):
        """Declare the winner (called from main thread)"""
        self.race_active = False
        self.status_label.config(
            text=f"🏆 Car {car_id + 1} WINS! 🏆",
            fg="gold",
            font=("Arial", 18, "bold")
        )
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        # Highlight winner
        self.draw_cars()
        

def main():
    """Main function to start the application"""
    root = tk.Tk()
    game = RacingGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
