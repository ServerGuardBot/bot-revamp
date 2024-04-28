SELECT * FROM feeddata WHERE
    time::now() > next_update;