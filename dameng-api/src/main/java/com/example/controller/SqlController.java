package com.example.controller;

import com.example.service.SqlService;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/sql")
@RequiredArgsConstructor
@Api(tags = "SQL执行接口")
public class SqlController {

    private final SqlService sqlService;

    @Data
    public static class SqlRequest {
        private String sql;
    }

    @Data
    public static class SqlV2Request {
        private String sql;
        private Integer limit = 20; // 默认限制20条
    }

    @Data
    public static class SqlV2Response {
        private List<Map<String, Object>> data;
        private long total;
    }

    @PostMapping("/execute")
    @ApiOperation(value = "执行SQL语句", notes = "执行传入的SQL语句并返回结果")
    public ResponseEntity<List<Map<String, Object>>> executeSql(@RequestBody SqlRequest request) {
        return ResponseEntity.ok(sqlService.executeSql(request.getSql()));
    }

    @PostMapping("/execute/v2")
    @ApiOperation(value = "执行SQL语句V2", notes = "执行传入的SQL语句并返回结果，支持限制返回条数和返回总数据量")
    public ResponseEntity<SqlV2Response> executeSqlV2(@RequestBody SqlV2Request request) {
        return ResponseEntity.ok(sqlService.executeSqlV2(request.getSql(), request.getLimit()));
    }
} 