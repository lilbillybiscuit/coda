use std::fs::File;
use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use matrixmultiply;

// Function to read a matrix from a file
fn read_matrix_from_file(filepath: &str) -> Result<Vec<Vec<f32>>, std::io::Error> {
    let path = Path::new(filepath);
    let file = File::open(&path)?;
    let reader = BufReader::new(file);
    let mut matrix = Vec::new();

    for line in reader.lines() {
        let line = line?;
        let row: Vec<f32> = line
            .split_whitespace()
            .filter_map(|s| s.parse::<f32>().ok())
            .collect();
        if !row.is_empty() {
            matrix.push(row);
        }
    }

    Ok(matrix)
}

// Function to write a matrix to a file
fn write_matrix_to_file(filepath: &str, matrix: &[Vec<f32>]) -> Result<(), std::io::Error> {
    let path = Path::new(filepath);
    let mut file = File::create(&path)?;

    for row in matrix {
        let line = row
            .iter()
            .map(|&val| val.to_string())
            .collect::<Vec<String>>()
            .join(" ");
        writeln!(file, "{}", line)?;
    }

    Ok(())
}

pub fn cacheaware_main() -> Result<(), std::io::Error> {
    // Read matrices from files
    let matrix_a = read_matrix_from_file("matrix_a.txt")?;
    let matrix_b = read_matrix_from_file("matrix_b.txt")?;

    // Get dimensions
    let a_rows = matrix_a.len();
    let a_cols = matrix_a[0].len();
    let b_cols = matrix_b[0].len();

    // Flatten matrices for matrixmultiply
    let flat_a: Vec<f32> = matrix_a.into_iter().flatten().collect();
    let flat_b: Vec<f32> = matrix_b.into_iter().flatten().collect();

    // Allocate output matrix
    let mut flat_c = vec![0.0; a_rows * b_cols];

    // Perform matrix multiplication with matrixmultiply
    unsafe {
        matrixmultiply::sgemm(
            a_rows, a_cols, b_cols,
            1.0,
            flat_a.as_ptr(), a_cols as isize, 1,
            flat_b.as_ptr(), b_cols as isize, 1,
            0.0,
            flat_c.as_mut_ptr(), b_cols as isize, 1
        )
    }

    // Reshape the result to a 2D matrix
    let result_matrix: Vec<Vec<f32>> = flat_c.chunks(b_cols).map(|row| row.to_vec()).collect();

    // Write the result to a file
    write_matrix_to_file("output.txt", &result_matrix)?;

    Ok(())
}