import numpy as np
import matplotlib.pyplot as plt
from typing import List, Tuple

class DartboardScoring:
    def __init__(self):
        """Initialize dartboard scoring measurements using regulation dimensions."""
        # Standard measurements in mm
        self.double_bull_radius = 12.7   # 25.4mm diameter
        self.bull_radius = 31.8          # 63.5mm diameter
        self.triple_inner_radius = 107   # 214mm diameter
        self.triple_outer_radius = 115   # 230mm diameter
        self.double_inner_radius = 162   # 324mm diameter
        self.double_outer_radius = 170.5  # 341mm diameter

        # Standard scoring segments (clockwise from top, 20 is at top)
        self.segments = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

    def get_score(self, x: float, y: float) -> str:
        """
        Determine the score for a dart at given x,y coordinates.
        
        Args:
            x: X coordinate in mm from center
            y: Y coordinate in mm from center
            
        Returns:
            str: Score description (e.g., "DOUBLE 20", "TRIPLE 5", "BULL", "DOUBLE BULL")
                 or "MISS" if outside scoring area
        """
        # Calculate distance from center and angle
        distance = np.sqrt(x**2 + y**2)
        # Fix mirroring by removing the negative x, and add 9 degree rotation
        angle = (np.degrees(np.arctan2(x, y)) + 9) % 360  # Convert to 0-360 degrees, 0 at top
        
        # Check if it's a miss (outside double ring)
        if distance > self.double_outer_radius:
            return "MISS"
            
        # Check for double bull (center)
        if distance <= self.double_bull_radius:
            return "DOUBLE BULL"
            
        # Check for bull (outer bull)
        if distance <= self.bull_radius:
            return "BULL"
            
        # Determine which segment (1-20) was hit
        segment_index = int(angle / 18)  # 360 degrees / 20 segments = 18 degrees per segment
        segment_number = self.segments[segment_index]
        
        # Determine multiplier (double/triple)
        if self.triple_inner_radius <= distance <= self.triple_outer_radius:
            return f"TRIPLE {segment_number}"
        elif self.double_inner_radius <= distance <= self.double_outer_radius:
            return f"DOUBLE {segment_number}"
        else:
            return str(segment_number)

    def get_score_value(self, score_str: str) -> int:
        """Convert score string to numerical value."""
        if score_str == "MISS":
            return 0
        elif score_str == "DOUBLE BULL":
            return 50
        elif score_str == "BULL":
            return 25
        else:
            parts = score_str.split()
            if len(parts) == 1:  # Single
                return int(parts[0])
            elif parts[0] == "DOUBLE":
                return 2 * int(parts[1])
            else:  # TRIPLE
                return 3 * int(parts[1])

    def visualize_board(self, dart_positions: List[Tuple[float, float]] = None,
                       save_path: str = 'dartboard_scoring.png'):
        """Visualize dartboard with optional dart positions."""
        plt.figure(figsize=(12, 12))
        
        # Draw circles for different scoring regions
        circles = [
            (self.double_outer_radius, 'black', 'Double Ring'),
            (self.double_inner_radius, 'white', None),
            (self.triple_outer_radius, 'black', 'Triple Ring'),
            (self.triple_inner_radius, 'white', None),
            (self.bull_radius, 'green', 'Bull'),
            (self.double_bull_radius, 'red', 'Double Bull')
        ]
        
        for radius, color, label in circles:
            circle = plt.Circle((0, 0), radius, fill=False, color=color,
                              label=label if label else None)
            plt.gca().add_artist(circle)
        
        # Draw segment lines and numbers with 9 degree offset
        for i in range(20):
            angle = np.radians(i * 18 - 9)  # 18 degrees per segment, -9 for correct orientation
            dx = np.sin(angle) * self.double_outer_radius
            dy = np.cos(angle) * self.double_outer_radius
            plt.plot([0, dx], [0, dy], 'k-', linewidth=0.5)
            
            # Add segment numbers
            text_radius = self.triple_inner_radius  # Place numbers between triple and double
            text_x = np.sin(angle + np.radians(9)) * text_radius  # +9 degrees for center of segment
            text_y = np.cos(angle + np.radians(9)) * text_radius
            plt.text(text_x, text_y, str(self.segments[i]), 
                    ha='center', va='center')
        
        # Plot dart positions if provided
        if dart_positions:
            for i, (x, y) in enumerate(dart_positions):
                score = self.get_score(x, y)
                plt.plot(x, y, 'ro', markersize=10, label=f'Dart {i+1}: {score}')
        
        plt.axis('equal')
        plt.grid(True)
        plt.title('Dartboard Scoring Regions')
        plt.xlabel('X Position (mm)')
        plt.ylabel('Y Position (mm)')
        
        # Set axis limits to show full board with some padding
        limit = self.double_outer_radius * 1.1
        plt.xlim(-limit, limit)
        plt.ylim(-limit, limit)
        
        plt.legend()
        plt.savefig(save_path)
        plt.close()
        print(f"Plot saved as '{save_path}'")


if __name__ == "__main__":
    # Create scoring instance
    scoring = DartboardScoring()
    
    # Example dart positions (x, y) in mm from center
    dart_positions = [
        (0, 0),           # Center (double bull)
        (0, 170),         # Straight up (should hit 20)
        (100, 0),         # Straight right (should hit 5)
        (-100, 0),        # Straight left (should hit 12)
        (0, -100),        # Straight down (should hit 3)
    ]
    
    # Get scores for each dart
    for i, pos in enumerate(dart_positions):
        score = scoring.get_score(pos[0], pos[1])
        value = scoring.get_score_value(score)
        print(f"Dart {i+1} at position {pos}: {score} ({value} points)")
    
    # Visualize the dartboard with these positions
    scoring.visualize_board(dart_positions)