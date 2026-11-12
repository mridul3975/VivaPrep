CREATE UNIQUE INDEX one_viva_followup_per_parent
ON repoviva.turns(owner, (payload->>'parent_turn_id'))
WHERE payload ? 'parent_turn_id';
