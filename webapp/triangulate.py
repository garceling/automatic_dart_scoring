import numpy as np
from typing import List, Tuple, Optional, Callable
import matplotlib.pyplot as plt

class DartPositionFinder:
    def __init__(self, num_cameras: int = 4, angle_spacing: float = 36, 
                 board_radius: float = 225.5, scoring_radius: float = 170.5,  # 451mm/2 and 341mm/2
                 camera_distance_factor: float = 1.9,
                 distortion_func: Optional[Callable[[float], float]] = None):
        """
        Initialize the dart position finder with camera positions.
        
        Args:
            num_cameras: Number of cameras
            angle_spacing: Angle between cameras in degrees
            board_radius: Total physical radius of the dart board in cm
            scoring_radius: Radius of the scoring area in cm
            camera_distance_factor: Factor of board radius at which cameras are placed
            distortion_func: Optional function to model camera distortion
                           Takes normalized position (0-1) and returns corrected position
        """
        self.num_cameras = num_cameras
        self.angle_spacing = np.deg2rad(angle_spacing)
        self.board_radius = board_radius
        self.scoring_radius = scoring_radius
        self.camera_radius = board_radius * camera_distance_factor
        self.distortion_func = distortion_func or (lambda x: x)  # Identity function if None
        
        # Calculate camera positions and their perpendicular viewing lines
        self.camera_positions = []
        self.camera_angles = []
        for i in range(num_cameras):
            angle = i * self.angle_spacing
            self.camera_positions.append((
                self.camera_radius * np.cos(angle),
                self.camera_radius * np.sin(angle)
            ))
            # Camera angles point inward
            self.camera_angles.append(angle + np.pi)

    def normalized_to_lateral(self, normalized_pos: float) -> float:
        """Convert normalized position (0-1) to lateral distance from camera centerline."""
        # Apply distortion correction
        corrected_pos = self.distortion_func(normalized_pos)
        # Convert from 0-1 range to actual lateral distance
        return (2 * corrected_pos - 1) * self.board_radius

    def point_in_scoring_area(self, point: Tuple[float, float]) -> bool:
        """Check if a point lies within the scoring area."""
        return np.sqrt(point[0]**2 + point[1]**2) <= self.scoring_radius
    
    def point_in_board(self, point: Tuple[float, float]) -> bool:
        """Check if a point lies within the physical board."""
        return np.sqrt(point[0]**2 + point[1]**2) <= self.board_radius

    def validate_readings(self, camera_readings: List[List[float]]) -> bool:
        """
        Validate camera readings format and values.
        
        Args:
            camera_readings: List of lists of normalized positions (0-1) from each camera
            
        Returns:
            bool: True if readings are valid
            
        Raises:
            ValueError: If readings are invalid, with explanation
        """
        # Check number of cameras
        if len(camera_readings) != self.num_cameras:
            raise ValueError(f"Expected {self.num_cameras} cameras, got {len(camera_readings)}")
            
        # Get number of darts (length of first camera's readings)
        if not camera_readings[0]:
            return True  # Empty readings are valid (no darts)
            
        num_darts = len(camera_readings[0])
        if num_darts > 3:
            raise ValueError(f"Maximum 3 darts allowed, got {num_darts}")
            
        # Check each camera's readings
        for i, readings in enumerate(camera_readings):
            # Check number of readings matches first camera
            if len(readings) != num_darts:
                raise ValueError(f"Camera {i} has {len(readings)} readings, expected {num_darts}")
                
            # Check each reading is in valid range (0 to 1)
            for j, pos in enumerate(readings):
                if not (0 <= pos <= 1):
                    raise ValueError(
                        f"Camera {i}, reading {j}: position {pos:.3f} is outside "
                        f"valid range (0 to 1)"
                    )
        
        return True

    def camera_line_equation(self, camera_idx: int, normalized_pos: float) -> Tuple[float, float, float]:
        """
        Get the line equation (ax + by + c = 0) for a camera's view line.
        
        Args:
            camera_idx: Index of the camera
            normalized_pos: Position from 0 (leftmost) to 1 (rightmost) in camera's view
            
        Returns:
            Tuple of (a, b, c) for line equation ax + by + c = 0
        """
        camera_angle = self.camera_angles[camera_idx]
        camera_pos = self.camera_positions[camera_idx]
        
        # Convert normalized position to lateral distance
        lateral_dist = self.normalized_to_lateral(normalized_pos)
        
        # Direction vector of camera's view (perpendicular to camera angle)
        dx = -np.sin(camera_angle)
        dy = np.cos(camera_angle)
        
        # Point on the view line at the given lateral distance
        point_on_line = (
            camera_pos[0] + lateral_dist * dx,
            camera_pos[1] + lateral_dist * dy
        )
        
        # Line equation coefficients
        a = dx
        b = dy
        c = -(a * point_on_line[0] + b * point_on_line[1])
        
        return (a, b, c)

    def line_intersection(self, line1: Tuple[float, float, float], 
                         line2: Tuple[float, float, float]) -> Optional[Tuple[float, float]]:
        """Find intersection of two lines given by their equations ax + by + c = 0."""
        a1, b1, c1 = line1
        a2, b2, c2 = line2
        
        det = a1 * b2 - a2 * b1
        if abs(det) < 1e-10:  # Lines are parallel
            return None
            
        x = (b1 * c2 - b2 * c1) / det
        y = (a2 * c1 - a1 * c2) / det
        
        return (x, y)

    def find_dart_positions(self, camera_readings: List[List[float]], 
                          tolerance: float = 0.1) -> List[Tuple[float, float]]:
        """
        Find dart positions from camera readings.
        
        Args:
            camera_readings: List of lists of normalized positions (0-1) from each camera.
                           0 = leftmost possible position in camera's view
                           1 = rightmost possible position in camera's view
            tolerance: Maximum distance between intersection points to be considered
                      the same dart
                      
        Returns:
            List of (x, y) positions for each detected dart (maximum 3)
        """
        # Validate readings first
        self.validate_readings(camera_readings)
        
        intersections = []
        
        # For each possible dart
        for dart_idx in range(len(camera_readings[0])):
            # Get all pairwise intersections for this dart
            dart_intersections = []
            
            # Compare each pair of cameras
            for i in range(self.num_cameras):
                for j in range(i + 1, self.num_cameras):
                    # Get line equations for both cameras' views of this dart
                    line1 = self.camera_line_equation(i, camera_readings[i][dart_idx])
                    line2 = self.camera_line_equation(j, camera_readings[j][dart_idx])
                    
                    # Find intersection
                    intersection = self.line_intersection(line1, line2)
                    if intersection and self.point_in_board(intersection):
                        dart_intersections.append(intersection)
            
            # If we found valid intersections for this dart
            if dart_intersections:
                # Average all intersection points for this dart
                avg_pos = (
                    np.mean([p[0] for p in dart_intersections]),
                    np.mean([p[1] for p in dart_intersections])
                )
                if self.point_in_board(avg_pos):
                    intersections.append(avg_pos)
        
        return intersections

    def visualize(self, camera_readings: List[List[float]], 
                 dart_positions: List[Tuple[float, float]], 
                 save_path: str = 'dart_positions.png'):
        """Visualize the dart board, cameras, and detected dart positions."""
        plt.figure(figsize=(10, 10))
        
        # Plot physical board circle (outer circle)
        board_circle = plt.Circle((0, 0), self.board_radius, fill=False, color='gray', 
                                label='Physical Board')
        plt.gca().add_artist(board_circle)
        
        # Plot scoring area circle (inner circle)
        scoring_circle = plt.Circle((0, 0), self.scoring_radius, fill=False, color='black',
                                  label='Scoring Area')
        plt.gca().add_artist(scoring_circle)
        
        # Plot non-scoring area with light gray fill
        non_scoring_ring = plt.Circle((0, 0), self.board_radius, fill=True, color='lightgray', alpha=0.3)
        scoring_area = plt.Circle((0, 0), self.scoring_radius, fill=True, color='white')
        plt.gca().add_artist(non_scoring_ring)
        plt.gca().add_artist(scoring_area)
        
        # Plot camera circle (dashed)
        camera_circle = plt.Circle((0, 0), self.camera_radius, fill=False, color='gray', 
                                 linestyle='--', label='Camera Circle')
        plt.gca().add_artist(camera_circle)
        
        # Plot cameras and their view lines
        for i, (pos, angle) in enumerate(zip(self.camera_positions, self.camera_angles)):
            # Plot camera
            plt.plot(pos[0], pos[1], 'bs', markersize=10)
            
            # Plot camera direction
            direction_length = 0.2 * self.board_radius
            plt.arrow(pos[0], pos[1], 
                     direction_length * np.cos(angle),
                     direction_length * np.sin(angle),
                     head_width=0.05 * self.board_radius, 
                     head_length=0.1 * self.board_radius, 
                     fc='b', ec='b')
            
            # Plot view lines for each dart reading
            for normalized_pos in camera_readings[i]:
                lateral_dist = self.normalized_to_lateral(normalized_pos)
                
                # Direction vector perpendicular to camera angle
                dx = -np.sin(angle)
                dy = np.cos(angle)
                
                # Point on the view line
                point = (pos[0] + lateral_dist * dx, pos[1] + lateral_dist * dy)
                
                # Plot perpendicular line through this point
                line_length = self.board_radius * 2
                plt.plot(
                    [point[0] - dy * line_length, point[0] + dy * line_length],
                    [point[1] + dx * line_length, point[1] - dx * line_length],
                    'g--', alpha=0.3
                )
        
        # Plot dart positions with different colors based on scoring vs non-scoring
        for pos in dart_positions:
            color = 'ro' if self.point_in_scoring_area(pos) else 'yo'
            label = 'Scoring Dart' if self.point_in_scoring_area(pos) else 'Non-scoring Dart'
            plt.plot(pos[0], pos[1], color, markersize=10, label=label)
            
        plt.grid(True)
        plt.axis('equal')
        plt.title('Dart Board with Detected Positions')
        plt.xlabel('X Position (cm)')
        plt.ylabel('Y Position (cm)')
        
        # Add legend with unique entries only
        handles, labels = plt.gca().get_legend_handles_labels()
        unique_labels = dict(zip(labels, handles))
        plt.legend(unique_labels.values(), unique_labels.keys())
        
        # Set axis limits to show full camera circle with some padding
        limit = self.camera_radius * 1.1
        plt.xlim(-limit, limit)
        plt.ylim(-limit, limit)
        
        # Save plot
        plt.savefig(save_path)
        plt.close()
        print(f"Plot saved as '{save_path}'")

# Example usage with 3 darts and optional distortion
if __name__ == "__main__":
    # Example of a barrel distortion function (disabled by default)
    def barrel_distortion(x: float, strength: float = 0.2) -> float:
        """
        Apply barrel distortion to normalized position.
        strength = 0: no distortion
        strength > 0: barrel distortion
        """
        return x + strength * (x - 0.5) * (x - 1) * x
    
    # Create finder instance with no distortion (using real dartboard measurements)
    finder = DartPositionFinder(
        board_radius=225.5,    # 451mm diameter / 2
        scoring_radius=170.5,  # 341mm diameter / 2
        camera_distance_factor=1.9,
        # distortion_func=lambda x: barrel_distortion(x, 0.2)  # Enable to test distortion
    )
    
    # Example camera readings (normalized 0-1 positions for 3 darts)
    camera_readings = [
        [0.3, 0.6, 0.8],  # Camera 0 sees darts at 30%, 60%, and 80% across its view
        [0.4, 0.5, 0.7],  # Camera 1's view of the same darts
        [0.2, 0.6, 0.9],  # Camera 2's view
        [0.3, 0.5, 0.8]   # Camera 3's view
    ]
    
    # Find dart positions
    dart_positions = finder.find_dart_positions(camera_readings)
    
    print("Detected dart positions (cm):", dart_positions)
    
    # Print whether each dart is in scoring area
    for i, pos in enumerate(dart_positions):
        status = "scoring" if finder.point_in_scoring_area(pos) else "non-scoring"
        print(f"Dart {i+1} is in {status} area")
    
    # Visualize results
    finder.visualize(camera_readings, dart_positions)