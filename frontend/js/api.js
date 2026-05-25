const BASE_URL = 'http://localhost:6545';

async function getAllJobs(){

    const response = await fetch(

        `${BASE_URL}/jobs/all`

    );

    return await response.json();

}

async function uploadResume(file, candidateName){

    const formData = new FormData();

    formData.append('file', file);

    formData.append('candidateName', candidateName);

    const response = await fetch(

        `${BASE_URL}/resume/upload`,

        {
            method:'POST',
            body:formData
        }

    );

    return await response.json();

}

async function getMatchScore(resumeId, jobId){

    const response = await fetch(

        `${BASE_URL}/match/${resumeId}/${jobId}`

    );

    return await response.json();

}