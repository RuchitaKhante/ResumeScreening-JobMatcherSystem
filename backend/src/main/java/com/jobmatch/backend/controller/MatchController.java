package com.jobmatch.backend.controller;

import com.jobmatch.backend.model.Job;
import com.jobmatch.backend.model.Resume;
import com.jobmatch.backend.repository.JobRepository;
import com.jobmatch.backend.repository.ResumeRepository;
import com.jobmatch.backend.service.MatchService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/api/match")
@CrossOrigin(origins = "*")
public class MatchController {

    @Autowired
    private MatchService matchService;

    @Autowired
    private ResumeRepository resumeRepository;

    @Autowired
    private JobRepository jobRepository;

    @GetMapping("/{resumeId}/{jobId}")
    public ResponseEntity<?> match(
            @PathVariable Long resumeId,
            @PathVariable Long jobId) {
        try {
            // Get resume from DB
            Resume resume = resumeRepository.findById(resumeId)
                .orElseThrow(() -> new RuntimeException("Resume not found"));

            // Get job from DB
            Job job = jobRepository.findById(jobId)
                .orElseThrow(() -> new RuntimeException("Job not found"));

            // Build job text
            String jobText = job.getTitle() + " " + job.getDescription() + " " + job.getRequiredSkills();

            // Call ML service with file path (String) and job text (String)
            Map<String, Object> result = matchService.getMatchScore(
                resume.getFilePath(), jobText);

            return ResponseEntity.ok(result);

        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }
}