FOR $field IN object::keys($settings) {
    //UPDATE type::thing("guild", $id) SET type::field($field) = $settings[$field];
    UPDATE type::thing("guild", $id) PATCH [
        {
            "op": "replace",
            "path": $field,
            "value": $settings[$field]
        }
    ];
}