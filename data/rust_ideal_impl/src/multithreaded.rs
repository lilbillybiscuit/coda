use std::fs::File;
use std::io::{self, BufRead, BufReader, Write};
use std::time::SystemTime;
use std::thread;
use std::sync::{mpsc, Arc};

fn read_matrix(filename: &str) -> io::Result<Vec<Vec<i32>>> {
    let file = File::open(filename)?;
    let reader = BufReader::new(file);
    let mut matrix = Vec::new();

    for line in reader.lines() {
        let line = line?;
        let row: Vec<i32> = line
            .split_whitespace()
            .map(|s| s.parse().unwrap())
            .collect();
        matrix.push(row);
    }

    Ok(matrix)
}

fn write_matrix(matrix: &Vec<Vec<i32>>, filename: &str) -> io::Result<()> {
    let mut file = File::create(filename)?;

    for row in matrix {
        let line: String = row.iter()
            .enumerate()
            .map(|(i, &val)| {
                if i == row.len() - 1 {
                    format!("{}", val)
                } else {
                    format!("{} ", val)
                }
            })
            .collect();
        writeln!(file, "{}", line)?;
    }

    Ok(())
}

// Multi Threaded
fn mat_mul_parallel(mat1: &Vec<Vec<i32>>, mat2: &Vec<Vec<i32>>) -> Option<Vec<Vec<i32>>> {
    let n = mat1.len();
    let m = mat2[0].len();
    let p = mat2.len();

    if mat1[0].len() != p {
        return None;
    }

    let thread_count = std::thread::available_parallelism().map_or(1, |n| n.get());;
    let mut threads = Vec::new();
    let (tx, rx) = mpsc::channel();
    let mat1 = Arc::new(mat1.clone());
    let mat2 = Arc::new(mat2.clone());

    for th in 0..thread_count {
        let tx = tx.clone();
        let mat1 = Arc::clone(&mat1);
        let mat2 = Arc::clone(&mat2);
        let start = (th * n) / thread_count;
        let end = ((th + 1) * n) / thread_count;

        threads.push(thread::spawn(move || {
            // println!("Thread {} processing rows {} to {}", th, start, end);
            let mut result = vec![vec![0; m]; n];

            for i in start..end {
                for j in 0..m {
                    let mut sum = 0;
                    for k in 0..p {
                        if mat1[i][k] != 0 && mat2[k][j] != 0 {
                            sum += mat1[i][k] * mat2[k][j];
                        }
                    }
                    result[i][j] = sum;
                }
            }

            tx.send((start, end, result)).unwrap();
        }));
    }

    let mut final_result = vec![vec![0; m]; n];
    for _ in 0..thread_count {
        let (start, end, partial_result) = rx.recv().unwrap();
        for i in start..end {
            final_result[i] = partial_result[i].clone();
        }
    }

    for handle in threads {
        handle.join().unwrap();
    }

    Some(final_result)
}

pub fn multithreaded_main() -> io::Result<()> {
    // Read input matrices
    let mat1 = read_matrix("matrix_a.txt")?;
    let mat2 = read_matrix("matrix_b.txt")?;

    let result = mat_mul_parallel(&mat1, &mat2);

    // Write result to file
    if let Some(result) = result {
        write_matrix(&result, "output.txt")?;
    } else {
        println!("Error: Incompatible matrix dimensions");
    }

    Ok(())
}