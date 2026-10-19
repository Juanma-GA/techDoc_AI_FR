use std::{
    io::{BufRead, BufReader, Write},
    net::{SocketAddr, TcpStream},
    time::Duration,
};

pub fn healthy(address: SocketAddr) -> bool {
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(300)) else {
        return false;
    };
    if stream
        .set_read_timeout(Some(Duration::from_millis(300)))
        .is_err()
        || stream
            .set_write_timeout(Some(Duration::from_millis(300)))
            .is_err()
    {
        return false;
    }
    if stream
        .write_all(
            format!("GET /api/v1/health HTTP/1.1\r\nHost: {address}\r\nConnection: close\r\n\r\n")
                .as_bytes(),
        )
        .is_err()
    {
        return false;
    }
    let mut status = String::new();
    BufReader::new(stream).read_line(&mut status).is_ok() && status.starts_with("HTTP/1.1 200 ")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{net::TcpListener, thread};

    fn responds_with(status: &'static str) -> bool {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let address = listener.local_addr().unwrap();
        let server = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            stream
                .set_read_timeout(Some(Duration::from_secs(2)))
                .unwrap();
            let mut request = BufReader::new(&mut stream);
            let mut line = String::new();
            request.read_line(&mut line).unwrap();
            assert!(line.starts_with("GET /api/v1/health "));
            loop {
                line.clear();
                request.read_line(&mut line).unwrap();
                if line == "\r\n" {
                    break;
                }
            }
            write!(stream, "HTTP/1.1 {status}\r\nContent-Length: 0\r\n\r\n").unwrap();
        });
        let ready = healthy(address);
        server.join().unwrap();
        ready
    }

    #[test]
    fn accepts_a_healthy_backend() {
        assert!(responds_with("200 OK"));
    }

    #[test]
    fn rejects_a_failed_backend() {
        assert!(!responds_with("503 Unavailable"));
    }
}
