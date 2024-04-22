DELETE image WHERE
    expires < time::now();