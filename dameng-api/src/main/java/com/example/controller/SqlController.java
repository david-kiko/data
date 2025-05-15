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

    @PostMapping("/execute")
    @ApiOperation(value = "执行SQL语句", notes = "执行传入的SQL语句并返回结果")
    public ResponseEntity<List<Map<String, Object>>> executeSql(@RequestBody SqlRequest request) {
        return ResponseEntity.ok(sqlService.executeSql(request.getSql()));
    }
} 