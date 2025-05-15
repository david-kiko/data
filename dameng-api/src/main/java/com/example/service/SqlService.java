package com.example.service;

import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class SqlService {

    private final JdbcTemplate jdbcTemplate;

    public List<Map<String, Object>> executeSql(String sql) {
        return jdbcTemplate.queryForList(sql);
    }
} 