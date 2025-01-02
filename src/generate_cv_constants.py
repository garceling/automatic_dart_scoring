"""
generate_cv_constants.py

Function:
This file's purpose is to generate a new yaml file to be used in the dart computer vision.
This new yaml file includes the new calcaulted parmaters from the values in the base yaml file
This code is standalone and must be run before running the main.py

"""
import yaml

def read_yaml(file_path):
    """Read data from a YAML file."""
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def write_yaml(data, file_path):
    """Write data to a YAML file."""
    with open(file_path, 'w') as file:
        yaml.dump(data, file, default_flow_style=False)

def calculate_constants(data):
    """Calculate new constants based on the loaded YAML data."""
    pixels_per_mm = data['IMAGE_HEIGHT'] / data['DARTBOARD_DIAMETER_MM']
    new_constants = {
        'PIXELS_PER_MM': pixels_per_mm,
        #convert mm measurements into pixels
        'BULLSEYE_RADIUS_PX': int(data['BULLSEYE_RADIUS_MM'] * pixels_per_mm),
        'OUTER_BULL_RADIUS_PX' : int(data['OUTER_BULL_RADIUS_MM'] * pixels_per_mm),
        'TRIPLE_RING_INNER_RADIUS_PX' : int(data['TRIPLE_RING_INNER_RADIUS_MM'] * pixels_per_mm),
        'TRIPLE_RING_OUTER_RADIUS_PX' : int(data['TRIPLE_RING_OUTER_RADIUS_MM'] * pixels_per_mm),
        'DOUBLE_RING_INNER_RADIUS_PX' : int(data['DOUBLE_RING_INNER_RADIUS_MM'] * pixels_per_mm),
        'DOUBLE_RING_OUTER_RADIUS_PX' : int(data['DOUBLE_RING_OUTER_RADIUS_MM'] * pixels_per_mm),
        'center' : tuple([data['IMAGE_WIDTH'] // 2, data['IMAGE_HEIGHT'] // 2])
    }
    return new_constants

input_yaml_file = 'config/cv_constants_base.yaml'
output_yaml_file = 'config/cv_constants.yaml'

original_data = read_yaml(input_yaml_file)

#calculte new constants based on the base yaml file
calculated_constants = calculate_constants(original_data)

# combine the base and calcualte data
combined_data = {
    **original_data,  
    **calculated_constants  
}

write_yaml(combined_data, output_yaml_file)

print(f"New YAML file written to {output_yaml_file}")
