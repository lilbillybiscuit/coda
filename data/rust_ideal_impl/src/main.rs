mod multithreaded;
mod strassen;
mod cacheaware;

use multithreaded::multithreaded_main;
use strassen::strassen_main;
use cacheaware::cacheaware_main;
use std::fs::File;
use std::io::{self, BufRead, BufReader, Write};
use std::time::Instant;



fn main() -> io::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    
    let start = Instant::now();

    if args.len() < 2 {
        eprintln!("Usage: {} <method>", args[0]);
        eprintln!("Methods: strassen, multithreaded, cacheaware");
        std::process::exit(1);
    }

    match args[1].as_str() {
        "strassen" => strassen_main()?,
        "multithreaded" => multithreaded_main()?,
        "cacheaware" => cacheaware_main()?,
        _ => {
            eprintln!("Unknown method: {}", args[1]);
            eprintln!("Methods: strassen, multithreaded, cacheaware");
            std::process::exit(1);
        }
    }
    
    let duration = start.elapsed();
    println!("time {}ms", duration.as_millis());

    Ok(())
}