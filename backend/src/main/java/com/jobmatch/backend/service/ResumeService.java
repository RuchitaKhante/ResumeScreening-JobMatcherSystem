package com.jobmatch.backend.service;

import com.jobmatch.backend.model.Resume;
import com.jobmatch.backend.repository.ResumeRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.LocalDateTime;
import java.util.List;

@Service
public class ResumeService {

    @Autowired
    private ResumeRepository resumeRepository;

    private final String UPLOAD_DIR = "uploads/";

    public Resume uploadResume(MultipartFile file, Long userId) throws Exception {
    // Create uploads folder
    File uploadDir = new File("uploads/");
    if (!uploadDir.exists()) {
        uploadDir.mkdirs();
    }

    // Save file
    String fileName = System.currentTimeMillis() + "_" + file.getOriginalFilename();
    String filePath = "uploads/" + fileName;
    file.transferTo(new File(filePath));

    // Save to DB
    Resume resume = new Resume();
    resume.setUserId(userId);
    resume.setFileName(file.getOriginalFilename());
    resume.setFilePath(filePath);
    resume.setExtractedText("");
    resume.setUploadedAt(java.time.LocalDateTime.now());

    return resumeRepository.save(resume);
}

    public List<Resume> getAllResumes() {
        return resumeRepository.findAll();
    }

    public Resume getResumeById(Long id) {
        return resumeRepository.findById(id)
            .orElseThrow(() -> new RuntimeException("Resume not found: " + id));
    }

    public void deleteResume(Long id) {
        resumeRepository.deleteById(id);
    }
}