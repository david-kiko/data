package com.example.service;

import com.example.controller.SqlController.SqlV2Response;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

@Service
@RequiredArgsConstructor
public class SqlService {

    private final JdbcTemplate jdbcTemplate;

    public List<Map<String, Object>> executeSql(String sql) {
        return jdbcTemplate.queryForList(sql);
    }

    public SqlV2Response executeSqlV2(String sql, Integer limit) {
        // 清理SQL语句：移除末尾的分号和LIMIT子句
        String cleanSql = sql.trim();
        if (cleanSql.endsWith(";")) {
            cleanSql = cleanSql.substring(0, cleanSql.length() - 1);
        }
        cleanSql = cleanSql.replaceAll("(?i)\\s+LIMIT\\s+\\d+\\s*$", "");

        // 获取总数据量
        String countSql = "SELECT COUNT(*) as total FROM (" + cleanSql + ") t";
        long total = jdbcTemplate.queryForObject(countSql, Long.class);

        // 如果limit为-1，则不限制返回条数
        if (limit != null && limit == -1) {
            List<Map<String, Object>> data = jdbcTemplate.queryForList(cleanSql);
            SqlV2Response response = new SqlV2Response();
            response.setData(data);
            response.setTotal(total);
            return response;
        }

        // 添加limit限制
        String limitedSql = cleanSql + " LIMIT " + limit;
        List<Map<String, Object>> data = jdbcTemplate.queryForList(limitedSql);
        
        SqlV2Response response = new SqlV2Response();
        response.setData(data);
        response.setTotal(total);
        return response;
    }
} 