package com.jobmatch.backend.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Table(name = "jobs")
@Data
@NoArgsConstructor
public class Job {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String title;
    private String company;
    @Column(columnDefinition = "TEXT")
    private String description;
    private String requiredSkills;
    private String location;
    private LocalDateTime postedAt;
}