import numpy as np

def read_matrix_from_file(filename):
    with open(filename, 'r') as file:
        return np.array([[int(num) for num in line.split()] for line in file])

def write_matrix_to_file(filename, matrix):
    with open(filename, 'w') as file:
        for row in matrix:
            file.write(' '.join(map(str, row)) + '\n')

if __name__ == "__main__":
    # Read matrices from files
    matrix_a = read_matrix_from_file('matrix_a.txt')
    matrix_b = read_matrix_from_file('matrix_b.txt')

    # Multiply matrices using NumPy
    result_matrix = np.dot(matrix_a, matrix_b)

    # Write result to output file
    write_matrix_to_file('output.txt', result_matrix)
