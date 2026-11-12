# Short spoken viva with one follow-up

The existing practice screen accepts microphone recordings, WAV uploads and
typing. Speech passes through the existing Prisma endpoint into the editable
answer field. No automatic submission is added: the student corrects the
transcript, then explicitly submits for source-backed feedback.

After reviewing an original answer, **Continue with a follow-up** requests one
question based on the submitted answer saved on the server and the same original
evidence packet. It includes a hidden reference answer and validated source-line
rubric. The student records or types their response and submits through the same
grading endpoint. Next question returns to the original question sequence.

Each original question has at most one child, with no recursive chain. A three
question set therefore has at most six turns. Follow-up results contribute to
the existing score. History restores each child immediately after its parent,
along with saved answers/feedback and the last visited turn. The earlier answer
is available in a disclosure. Re-answering a parent does not regenerate its child:
the child remains bound to the submitted answer used when it was created.

## Persistence, limits and errors

This extension requires PostgreSQL, as History/Debug already do. Apply migration
005 before serving traffic. The unique parent index and existing turn leases
prevent duplicate concurrent generations. Follow-ups remain in the same owned
practice set, with the original source revision and evidence. The server reads
the saved answer; callers cannot substitute another answer or evidence packet.
References/rubrics stay hidden until the follow-up is submitted for evaluation.

Personal-file follow-up creation uses one question-set allowance, disclosed at
the action. Its answer uses the normal review allowance; recording uses the
existing transcription allowance. Reopening a saved child is free. Known provider
or citation failures refund generation, release the lease and preserve the prior
feedback. Students may retry or skip to the next original question. Guest shared
ceilings apply as for ordinary question generation.

The Python demo has an explicitly prepared, free Boolean follow-up that selects
a contrasting prime/square input according to the answer. It does not claim to
be AI-generated. Its grading stays deterministic. Guests still have one daily
transcription by default; subsequent answers can be typed or the student can
sign in for account allowances.

## Verification

122 backend regression tests passed, including five follow-up tests for ownership,
CSRF, submission ordering, source/answer binding, hidden references, caching,
quota refunds, persistence ordering and rejection of invalid citations.
Build and lint passed. A real Groq call challenged the incorrect claim that
nine is prime because it is odd by asking the learner to trace `is_prime(9)`;
all returned rubric quotes matched the source.

Browser checks used actual local Flask/PostgreSQL and guest cookies at
1440/390/360px. A valid WAV exercised the transcription endpoint with a simulated
transcriber, then the learner edited and explicitly submitted it, answered a
follow-up, reloaded and continued to the next original question. No physical
microphone or live STT call was exercised in this change. This does not add
speech synthesis, streaming voice chat, automatic transcript confidence analysis,
Debug explanation assessment or user-study findings.
