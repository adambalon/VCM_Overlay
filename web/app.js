// Load the pending submissions
async function loadPendingSubmissions() {
  try {
    const response = await fetch('data/pending.json');
    const data = await response.json();
    displayPendingSubmissions(data.submissions);
  } catch (error) {
    console.error('Error loading pending submissions:', error);
    document.getElementById('pending-list').innerHTML = 
      '<p>Error loading submissions. Please try again later.</p>';
  }
}

// Display the list of pending submissions
function displayPendingSubmissions(submissions) {
  const pendingList = document.getElementById('pending-list');
  pendingList.innerHTML = '';
  
  if (!submissions || submissions.length === 0) {
    pendingList.innerHTML = '<p>No pending submissions</p>';
    return;
  }
  
  // Filter for pending submissions
  const pendingSubmissions = submissions.filter(s => s.status === 'pending');
  
  if (pendingSubmissions.length === 0) {
    pendingList.innerHTML = '<p>No pending submissions</p>';
    return;
  }
  
  pendingSubmissions.forEach(submission => {
    const submissionElement = document.createElement('div');
    submissionElement.className = 'submission-item';
    submissionElement.innerHTML = `
      <h3>${submission.type.toUpperCase()} Parameter #${submission.param_id}</h3>
      <p>${submission.name}</p>
      <button onclick="viewSubmission('${submission.id}')">View Details</button>
    `;
    pendingList.appendChild(submissionElement);
  });
}

// View a specific submission
async function viewSubmission(submissionId) {
  try {
    const response = await fetch('data/pending.json');
    const data = await response.json();
    const submission = data.submissions.find(s => s.id === submissionId);
    
    if (submission) {
      displaySubmissionDetails(submission);
    } else {
      document.getElementById('submission-details').innerHTML = 
        '<p>Submission not found</p>';
    }
  } catch (error) {
    console.error('Error loading submission details:', error);
    document.getElementById('submission-details').innerHTML = 
      '<p>Error loading submission details. Please try again later.</p>';
  }
}

// Display the details of a submission
function displaySubmissionDetails(submission) {
  const detailsSection = document.getElementById('submission-details');
  
  detailsSection.innerHTML = `
    <div class="submission-detail">
      <h3>${submission.type.toUpperCase()} Parameter #${submission.param_id}</h3>
      <p><strong>Name:</strong> ${submission.name}</p>
      <p><strong>Description:</strong> ${submission.description || 'No description provided'}</p>
      <div>
        <strong>Details:</strong>
        <pre class="details-box">${submission.details || 'No details provided'}</pre>
      </div>
      <p><strong>Submitted:</strong> ${new Date(submission.timestamp).toLocaleString()}</p>
      
      <div class="action-buttons">
        <button onclick="approveSubmission('${submission.id}')">Approve</button>
        <button onclick="rejectSubmission('${submission.id}')">Reject</button>
      </div>
    </div>
  `;
}

// Approve a submission - simplified version for now
function approveSubmission(submissionId) {
  alert('In a real implementation, this would approve the submission and update the parameter file.');
  console.log('Approving submission:', submissionId);
  
  // For demo purposes, we'll update the UI as if it worked
  document.getElementById('submission-details').innerHTML = 
    '<p>Submission approved! (This is just a demo - the files are not actually updated)</p>';
  loadPendingSubmissions();
}

// Reject a submission - simplified version for now
function rejectSubmission(submissionId) {
  alert('In a real implementation, this would reject the submission.');
  console.log('Rejecting submission:', submissionId);
  
  // For demo purposes, we'll update the UI as if it worked
  document.getElementById('submission-details').innerHTML = 
    '<p>Submission rejected! (This is just a demo - the files are not actually updated)</p>';
  loadPendingSubmissions();
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
  loadPendingSubmissions();
}); 