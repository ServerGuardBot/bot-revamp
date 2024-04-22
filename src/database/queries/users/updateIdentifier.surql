UPDATE type::thing("user_identifier", $id) SET
    uses_vpn = $vpn,
    hashed_ip = $ip,
    browser_id = $browser;