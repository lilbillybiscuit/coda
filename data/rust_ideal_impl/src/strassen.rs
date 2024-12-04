use std::fs::File;
use std::io::{self, BufRead, BufReader, Write};

#[derive(Debug, Clone)]
struct Matrix {
    rows: usize,
    cols: usize,
    data: Vec<i32>,
}

impl Matrix {
    fn new(rows: usize, cols: usize) -> Self {
        Matrix {
            rows,
            cols,
            data: vec![0; rows * cols],
        }
    }

    fn get(&self, i: usize, j: usize) -> i32 {
        self.data[i * self.cols + j]
    }

    fn set(&mut self, i: usize, j: usize, val: i32) {
        self.data[i * self.cols + j] = val;
    }

    fn from_file(filename: &str) -> io::Result<Self> {
        let file = File::open(filename)?;
        let reader = BufReader::new(file);
        let mut rows = Vec::new();

        for line in reader.lines() {
            let line = line?;
            let row: Vec<i32> = line
                .split_whitespace()
                .map(|s| s.parse().unwrap())
                .collect();
            rows.push(row);
        }

        let n_rows = rows.len();
        let n_cols = rows[0].len();
        let mut matrix = Matrix::new(n_rows, n_cols);

        for i in 0..n_rows {
            for j in 0..n_cols {
                matrix.set(i, j, rows[i][j]);
            }
        }

        Ok(matrix)
    }

    fn to_file(&self, filename: &str) -> io::Result<()> {
        let mut file = File::create(filename)?;

        for i in 0..self.rows {
            let mut line = String::new();
            for j in 0..self.cols {
                line.push_str(&format!("{:.1} ", self.get(i, j)));
            }
            line.push('\n');
            file.write_all(line.as_bytes())?;
        }

        Ok(())
    }

    fn standard_multiply(&self, other: &Matrix) -> Option<Matrix> {
        if self.cols != other.rows {
            return None;
        }

        let mut result = Matrix::new(self.rows, other.cols);

        for i in 0..self.rows {
            for j in 0..other.cols {
                let mut sum = 0;
                // Skip computation if either element is zero
                for k in 0..self.cols {
                    let a = self.get(i, k);
                    if a != 0 {
                        let b = other.get(k, j);
                        if b != 0 {
                            sum += a * b;
                        }
                    }
                }
                result.set(i, j, sum);
            }
        }

        Some(result)
    }

    fn strassen_multiply(&self, other: &Matrix) -> Option<Matrix> {
        if self.cols != other.rows {
            return None;
        }

        // Use standard multiplication for small matrices
        const STRASSEN_THRESHOLD: usize = 64;
        if self.rows <= STRASSEN_THRESHOLD || self.cols <= STRASSEN_THRESHOLD || other.cols <= STRASSEN_THRESHOLD {
            return self.standard_multiply(other);
        }

        // Pad matrices to nearest power of 2
        let max_dim = self.rows.max(self.cols).max(other.cols);
        let n = max_dim.next_power_of_two();

        let mut a = self.pad_to_square(n);
        let mut b = other.pad_to_square(n);

        let mut result = strassen_recursive(&a, &b);

        // Trim result back to original dimensions
        result.rows = self.rows;
        result.cols = other.cols;
        result.data = result.unpad(self.rows, other.cols);

        Some(result)
    }

    fn pad_to_square(&self, n: usize) -> Matrix {
        let mut padded = Matrix::new(n, n);

        for i in 0..self.rows {
            for j in 0..self.cols {
                padded.set(i, j, self.get(i, j));
            }
        }

        padded
    }

    fn unpad(&self, rows: usize, cols: usize) -> Vec<i32> {
        let mut result = vec![0; rows * cols];
        for i in 0..rows {
            for j in 0..cols {
                result[i * cols + j] = self.get(i, j);
            }
        }
        result
    }
}

fn strassen_recursive(a: &Matrix, b: &Matrix) -> Matrix {
    let n = a.rows;
    if n <= 64 {
        return a.standard_multiply(b).unwrap();
    }

    let m = n / 2;

    // Divide matrices into quadrants
    let (a11, a12, a21, a22) = split_matrix(a);
    let (b11, b12, b21, b22) = split_matrix(b);

    // Compute the 7 products
    let p1 = strassen_recursive(&add_matrices(&a11, &a22), &add_matrices(&b11, &b22));
    let p2 = strassen_recursive(&add_matrices(&a21, &a22), &b11);
    let p3 = strassen_recursive(&a11, &sub_matrices(&b12, &b22));
    let p4 = strassen_recursive(&a22, &sub_matrices(&b21, &b11));
    let p5 = strassen_recursive(&add_matrices(&a11, &a12), &b22);
    let p6 = strassen_recursive(&sub_matrices(&a21, &a11), &add_matrices(&b11, &b12));
    let p7 = strassen_recursive(&sub_matrices(&a12, &a22), &add_matrices(&b21, &b22));

    // Compute quadrants of result
    let c11 = add_matrices(&sub_matrices(&add_matrices(&p1, &p4), &p5), &p7);
    let c12 = add_matrices(&p3, &p5);
    let c21 = add_matrices(&p2, &p4);
    let c22 = add_matrices(&sub_matrices(&add_matrices(&p1, &p3), &p2), &p6);

    // Combine quadrants into result
    combine_matrices(&c11, &c12, &c21, &c22)
}

fn split_matrix(matrix: &Matrix) -> (Matrix, Matrix, Matrix, Matrix) {
    let m = matrix.rows / 2;
    let mut a11 = Matrix::new(m, m);
    let mut a12 = Matrix::new(m, m);
    let mut a21 = Matrix::new(m, m);
    let mut a22 = Matrix::new(m, m);

    for i in 0..m {
        for j in 0..m {
            a11.set(i, j, matrix.get(i, j));
            a12.set(i, j, matrix.get(i, j + m));
            a21.set(i, j, matrix.get(i + m, j));
            a22.set(i, j, matrix.get(i + m, j + m));
        }
    }

    (a11, a12, a21, a22)
}

fn add_matrices(a: &Matrix, b: &Matrix) -> Matrix {
    let mut result = Matrix::new(a.rows, a.cols);
    for i in 0..a.rows {
        for j in 0..a.cols {
            result.set(i, j, a.get(i, j) + b.get(i, j));
        }
    }
    result
}

fn sub_matrices(a: &Matrix, b: &Matrix) -> Matrix {
    let mut result = Matrix::new(a.rows, a.cols);
    for i in 0..a.rows {
        for j in 0..a.cols {
            result.set(i, j, a.get(i, j) - b.get(i, j));
        }
    }
    result
}

fn combine_matrices(c11: &Matrix, c12: &Matrix, c21: &Matrix, c22: &Matrix) -> Matrix {
    let n = c11.rows * 2;
    let mut result = Matrix::new(n, n);

    for i in 0..c11.rows {
        for j in 0..c11.cols {
            result.set(i, j, c11.get(i, j));
            result.set(i, j + c11.cols, c12.get(i, j));
            result.set(i + c11.rows, j, c21.get(i, j));
            result.set(i + c11.rows, j + c11.cols, c22.get(i, j));
        }
    }

    result
}

pub fn strassen_main() -> io::Result<()> {
    println!("Strassen multiplication");
    use std::time::Instant;

    // Read input matrices
    let start = Instant::now();
    let matrix_a = Matrix::from_file("matrix_a.txt")?;
    let matrix_b = Matrix::from_file("matrix_b.txt")?;
    let duration = start.elapsed();
    // Choose multiplication method based on matrix size
    let start = Instant::now();
    let result = if matrix_a.rows < 64 || matrix_a.cols < 64 || matrix_b.cols < 64 {
        matrix_a.standard_multiply(&matrix_b)
    } else {
        matrix_a.strassen_multiply(&matrix_b)
    };
    let duration = start.elapsed();

    // Write result to output file
    if let Some(result) = result {
        result.to_file("output.txt")?;
    } else {
        println!("Error: Incompatible matrix dimensions");
    }

    Ok(())
}