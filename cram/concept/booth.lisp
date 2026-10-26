;;; booth.lisp -- the cotton candy booth in the conceptual CRAM layer (M1, step 2: schema library + servant table)
;;;
;;; Notation and decisions: concept document "A Conceptual CRAM Layer" (claude.ai/artifact/DaTuYZ6ftPF8YSJ1kuCmHE),
;;; section 2 (D1-D8, decided 2026-10-21) and section 4b (tree notation).
;;;   D1  designators: KR3 facets <kappa R I C Phi beta pi>, HADL syntax; schemas own kappa R I C Phi
;;;   D2  a/an attributive, the referential, its = belonging place
;;;   D3  bind (climb, monotone, retract only by repair) vs equate (co-reference)
;;;   D4  pre-act-verdict vs episode-verdict
;;;   D5  RWMS_beta = ME <-> BWS_beta; problems are assessed-against, outside the system
;;;   D6  the 8 AICOR admissibility conditions are the commitment gate
;;;   D7  context-indexed belonging, servants: norm > class home > storage zone > abstain
;;;   D8  force corridors belong to the body-world coupling, computed by microtheories
;;;   D9  the language is derived from the ontology (ontology/*.ttl, tools/ccram_lang.py lint)
;;;   D10 goals are templates of state evolutions over an interval (achieve / maintain / prevent / monitor / protect /
;;;       each); perform infers the goal from the schema's :telos template, achieve-family goals are refined into
;;;       action designators, protections, gate constraints, monitors (tools/ccram_goals.py)
;;;   Q2  modes stay physical; a deviation signals a typed failure description, the enclosing plan catches and handles
;;;       it (fault during service, intended burn-out at closing); closing events are prevented, never handled
;;; Sources inside CottonCandyTwin (the content below is a re-statement of them, not new domain knowledge):
;;;   cram/cotton_candy/semantic_annotations.py   object classes and part structure
;;;   cram/cotton_candy/manipulation_categories.py the categories (CategorySpecification: parent, effect, subactions,
;;;                                                telos state, roles, defined_in)
;;;   cram/cotton_candy/actions.py                 top-level designators (category compositions, manual pp. 5, 8-13)
;;;   cram/cotton_candy/process.py                 floss machine process model (phases, timings from the register)
;;;   cram/plans/make-and-hand-over.lisp           the generalized plan (triangle table, protections)
;;; Status: PROPOSAL for review. Numbers carry the register status of their source; servant costs are ILLUSTRATIVE.

(in-package :conceptual-cram)

;;; ================================================================================================================
;;; 1. The system and its problems (D5)
;;; ================================================================================================================

(:tag booth-shift
  (rwms
    (:boundary (objects booth machine sugar-carton-raspberry stick-quiver sugar-tray sponge work-table
                        handover-zone sales-flap customer-1 customer-2)
               (channels vision joint-state)           ; no force-torque in the kinematic baseline (see 6)
               (excluded weather crowd money))
    (:me  (cram-executive (body pr2) (plan-library booth-plans) (designator-kernel kr3-hadl)))
    (:bws (body pr2) (world booth))))

(assessed-against booth-shift
  (problem serve-orders
    (each ?candy (a cotton-candy (ordered-by ?customer))           ; D10: one sub-trajectory per ordered candy
      (achieve (delivered ?candy ?customer)))
    (maintain (clean booth))
    (prevent  (poured-into (some sugar) (tagged spinner-head machine) (phase (not off)))   ; SugarPouredIntoSpinningHead
              (contact (a person) (tagged spinner-head machine) (phase (not off)))       ; burn / spinning head
              (dropped (a cotton-candy)) (spilled (some sugar) floor))))

(assessed-against booth-shift
  (problem close-for-the-day
    (achieve  (burnt-out machine) (mode floss-machine off) (clean (tagged floss-pan machine)))
    (achieve  (at (each tool) (its destination)))      ; D7: context closed
    (prevent  (contact (a person) (tagged spinner-head machine) (phase (not off))))))

;;; ================================================================================================================
;;; 2. The booth as a tagged tree (part-whole; names are tags, paths implicit -- section 4b)
;;;    grounding: (annotation CLASS FIELD-PATH) names the semantic annotation of the CRAM world
;;;    (semantic_annotations.py); (body NAME) names the SDT body (PrefixedName(name, "booth")).
;;; ================================================================================================================

(:tag booth
 (node (is-a cc:cotton-candy-booth) (grounding (annotation CottonCandyBooth root))
  (parts
   (:tag machine
    (node (is-a cc:cotton-candy-machine) (grounding (annotation CottonCandyMachine root))
     (parts
      (:tag motor-switch (node (is-a cc:rocker-switch) (grounding (annotation CottonCandyMachine motor_switch))
                          (state on-off) (attribute label "Motor & Master" :status sourced :source GM_MAN_EXP)))
      (:tag heat-switch  (node (is-a cc:rocker-switch) (grounding (annotation CottonCandyMachine heat_switch))
                          (state on-off) (attribute label "Heat" :status sourced :source GM_MAN_EXP)))
      (:tag heat-control (node (is-a cc:control-knob) (grounding (annotation CottonCandyMachine heat_control))
                          (state travel-fraction)))
      (:tag spinner-head (node (is-a cc:spinner-head) (grounding (annotation CottonCandyMachine spinner_head))
                          (attribute capacity 0.060-kg :status calibrated :source head_sugar_capacity)))
      (:tag floss-pan    (node (is-a cc:floss-pan) (grounding (annotation CottonCandyMachine floss_pan))))
      (:tag lock-handles (node (is-a cc:lock-handle) (grounding (annotation CottonCandyMachine lock_handles)))))))
   (:tag sales-flap    (node (is-a cc:sales-flap) (grounding (annotation CottonCandyBooth sales_flap))
                        (parts (:tag handle (node (is-a sdt:handle))))))
   (:tag handover-zone (node (is-a cc:handover-zone)))
   (:tag stick-quiver  (node (is-a cc:stick-quiver)
                        (parts (:tag stick-1 (node (is-a cc:candy-stick) (parts (:tag tip (node (is-a sdt:tool-frame))))))
                               (:tag stick-2 (node (is-a cc:candy-stick) (parts (:tag tip (node (is-a sdt:tool-frame)))))))))
   (:tag sugar-carton-raspberry (node (is-a cc:sugar-carton) (attribute contains raspberry-flossugar)
                                 (parts (:tag spout (node (is-a sdt:tool-frame) (grounding (body "SugarCarton_end_effector")))))))
   (:tag sugar-tray    (node (is-a cc:sugar-tray)))
   (:tag sponge        (node (is-a cc:sponge)))
   (:tag work-table    (node (is-a sdt:table)))
   (:tag handwash-station (node (is-a cc:handwash-station)))
   (:tag fire-extinguisher (node (is-a cc:fire-extinguisher)))
   (:tag information-board (node (is-a cc:information-board)))
   (:tag stations (node (is-a cc:robot-stations)            ; layout ROBOT_STATIONS (x y yaw in the booth frame)
                   (parts (:tag at-machine (node (is-a cc:robot-station)))
                          (:tag machine-close (node (is-a cc:robot-station)))
                          (:tag serving (node (is-a cc:robot-station)))))))))

;; the robot, the same way (SDT robot parts; first robot of the world is the one CRAMERA binds)
(:tag pr2
 (node (is-a sdt:pr2)
  (parts (:tag left-arm  (node (is-a sdt:arm) (parts (:tag gripper (node (is-a sdt:end-effector))))))
         (:tag right-arm (node (is-a sdt:arm) (parts (:tag gripper (node (is-a sdt:end-effector))))))
         (:tag torso (node (is-a sdt:torso))) (:tag head (node (is-a sdt:neck) (parts (:tag camera (node (is-a sdt:camera))))))
         (:tag base (node (is-a sdt:mobile-base))))))

;;; ================================================================================================================
;;; 3. The floss machine microtheory (process.py; executable model = FlossMachineProcess)
;;; ================================================================================================================

(def-microtheory floss-machine
  (:regime material-process)
  (:quantities (sugar-in-head kg) (floss-in-pan kg) (burnt-out s))
  (:modes                                                              ; FlossMachinePhase, with KR3 mode classes
    (off           :when (not (on (tagged motor-switch machine)))                         :class safe)
    (spinning      :when (and (on motor-switch) (not (on heat-switch)))                   :class safe)
    (warming-up    :when (and (on motor-switch) (on heat-switch) (< heat-on 25-s))        :class safe)
    (producing     :when (and (on motor-switch) (on heat-switch) (>= heat-on 25-s) (> sugar-in-head 0))
                   :class safe)
    (running-empty :when (and (on motor-switch) (on heat-switch) (= sugar-in-head 0))
                   :class recoverable :signals head-running-empty))   ; Q2: the handler in scope decides fault vs intent
  (:timings (master-to-heat-delay 10-s) (warm-up 25-s :status sourced)
            (output-rate 2.5-portions/min :status sourced :source op_output_rate)
            (portion-sugar 0.020-kg) (head-capacity 0.060-kg :status calibrated) (fill-fraction 0.90 :status sourced)
            (burn-out 210-s :status sourced :source op_burnout_clean_min) (cool-down 90-s))
  (:closing-events                                                     ; recoverability-closing (KR3 section 4)
    (pour-into-moving-head :guard (and (poured-into sugar spinner-head) (not (mode off)))
                           :into prohibited :signals SugarPouredIntoSpinningHead)
    (contact-spinning-head :guard (and (contact any-person-or-robot spinner-head) (not (mode off)))
                           :into prohibited))
  (:observables (switch-positions joint-state) (floss-in-pan vision) (sugar-in-head model-only))
  (:executable FlossMachineProcess :file "cram/cotton_candy/process.py"))

;;; Failure descriptions of the booth (Q2). Classes in ontology/booth.ttl; executable classes in process.py.
(def-failure head-running-empty
  (:specializes process-failure)
  (:signalled-by (microtheory floss-machine) (:on-entry running-empty))
  (:describes (machine ?m) (since ?t) (floss-in-pan ?kg))
  (:suggests (seq stop-machine fill-spinner-head start-machine)))

(def-failure phase-not-reached
  (:specializes process-failure)
  (:signalled-by (action monitoring-process) (:timeout ?until))
  (:describes (expected ?phase) (actual ?phase)))

(def-failure not-enough-floss
  (:specializes process-failure)
  (:signalled-by (action gathering))
  (:describes (available ?kg) (required ?kg))
  (:suggests (seq (wait-for (portion-spun floss-machine)) retry)))

(def-failure navigation-blocked
  (:specializes navigation-failure)
  (:signalled-by (action navigating))
  (:describes (destination ?d) (blocked-by ?x)))

(def-failure sugar-poured-into-spinning-head
  (:specializes closing-event-violation)                 ; never handled: the gate prevents pour-into-moving-head
  (:signalled-by (microtheory floss-machine) (:closing-event pour-into-moving-head)))

;;; ================================================================================================================
;;; 4. The category lattice (manipulation_categories.py: CategorySpecification; defined_in kept)
;;; ================================================================================================================

(def-category-lattice booth-categories
  (transporting        (:specializes object-displacement)  (:sub reaching grasping lifting)  (:telos-state placed)
                       (:defined-in action-category-dl))
  (putting-down        (:specializes object-displacement)  (:sub reaching releasing)         (:telos-state placed)
                       (:defined-in action-category-dl))
  (pressing-button     (:specializes configuration-change) (:sub reaching pushing)           (:telos-state switched)
                       (:defined-in proposed))
  (turning             (:specializes configuration-change) (:sub reaching grasping rotating) (:telos-state set)
                       (:defined-in proposed))
  (scooping            (:specializes transferring)         (:sub reaching stroking lifting)  (:telos-state contained)
                       (:defined-in proposed))
  (pouring-into        (:specializes transferring pouring) (:sub grasping tilting)           (:telos-state accumulated)
                       (:defined-in action-category-dl))
  (gathering           (:specializes transferring)         (:sub reaching stroking lifting)  (:telos-state accumulated)
                       (:defined-in proposed))
  (wrapping            (:specializes substance-manipulation) (:sub stroking)                 (:telos-state shaped)
                       (:defined-in proposed))
  (handing-over        (:specializes interaction-action)   (:sub reaching releasing)         (:telos-state received)
                       (:defined-in proposed))
  (wiping              (:specializes surface-treatment)    (:sub grasping stroking)          (:telos-state clean)
                       (:defined-in action-category-dl))
  (monitoring-process  (:specializes perception-action)    (:sub)                            (:telos-state observed)
                       (:defined-in proposed)))

;;; ================================================================================================================
;;; 5. Action schemas: the invariant part of every booth action (D1)
;;;    phases name the giskard nodes the coraplex realisation compiles to (manipulation_categories.py)
;;; ================================================================================================================

(def-action-schema navigating                                                       ; Q3 (settled by D10)
  (:roles (destination (a station)))
  (:telos (:over ?i) (achieve (at (the robot) ?destination) :at (end ?i))
                     (prevent (contact (the robot) (a person)) :during ?i))
  (:causal (:regime locomotion))
  (:failures (navigation-blocked NavigationBlocked))
  (:phases (phase plan  (goal (path-to ?destination)))
           (phase drive (goal (at (the robot) ?destination)) (monitor path-clear) (terminal arrived))))

(def-action-schema transporting
  (:specializes object-displacement)
  (:roles (object (a graspable)) (arm (an arm (free t))) (approach (an approach-direction)))
  (:telos (:over ?i) (achieve (held-by ?object ?arm) :at (end ?i))
                     (prevent (dropped ?object) :during ?i))
  (:pre   (gripper-free ?arm))
  (:causal (:regime contact-transmission) (:corridor (grip ?object (tagged gripper ?arm))))    ; D8
  (:phases (phase reach (goal (pre-grasp ?object ?arm)) (giskard CartesianPose))
           (phase grasp (goal (force-closure ?arm ?object)) (giskard MoveGripperMotion) (monitor gripper-stall))
           (phase lift  (goal (lifted ?object)) (terminal (held-by ?object ?arm)))))

(def-action-schema putting-down
  (:specializes object-displacement)
  (:roles (object (the object (held-by ?arm))) (arm (an arm)) (destination (its destination)))   ; D7
  (:telos (:over ?i) (achieve (on ?object ?destination) :at (end ?i))
                     (achieve (gripper-free ?arm) :at (end ?i))
                     (prevent (dropped ?object) :during ?i))
  (:pre   (held-by ?object ?arm))
  (:admissible-refinement (pl1 support stability collision-free containment orientation reachable releasable future-access))
  (:causal (:regime contact-transmission))
  (:phases (phase lower   (goal (above ?object ?destination 0.01)) (giskard CartesianPose))
           (phase release (goal (released ?object)) (giskard MoveGripperMotion) (terminal (supported ?object)))))

(def-action-schema pressing-button
  (:specializes configuration-change)
  (:roles (object (a rocker-switch)) (arm (an arm (free t))) (state (a switch-state)))
  (:pre    (at (the robot) (the station (tag at-machine))))                     ; the controls / the pan are reached from the machine
  (:telos (:over ?i) (achieve (switch-state ?object ?state) :at (end ?i)))
  (:causal (:regime kinematic-constraint) (:template (rest -push[travel > detent]-> switched)))
  (:phases (phase reach (goal (finger-at ?object)) (giskard MoveTCPMayTouchMotion))
           (phase push  (goal (joint-at ?object ?state)) (giskard TurnToMotion/Open) (terminal switched))))

(def-action-schema turning
  (:specializes configuration-change)
  (:roles (object (a control-knob)) (arm (an arm (free t))) (setting (a travel-fraction)))
  (:pre    (at (the robot) (the station (tag at-machine))))                     ; the controls / the pan are reached from the machine
  (:telos (:over ?i) (achieve (travel-fraction ?object ?setting) :at (end ?i)))
  (:causal (:regime kinematic-constraint))
  (:phases (phase grasp  (goal (force-closure ?arm ?object)) (giskard MoveGripperMotion))
           (phase rotate (goal (joint-at ?object ?setting)) (giskard TurnToMotion/Open) (terminal set))
           (phase let-go (goal (released ?object)))))

(def-action-schema pouring-into
  (:specializes transferring pouring)
  (:roles (object (a sugar-carton (held-by ?arm))) (destination (a container)) (amount (some substance)))
  (:telos (:over ?i) (achieve  (contains ?destination ?amount) :at (end ?i))
                     (maintain (held-by ?object ?arm) :during ?i)
                     (prevent  (spilled ?amount) :during ?i)
                     (prevent  (poured-into ?amount ?destination) :while (not (mode floss-machine off))))
  (:pre   (and (held-by ?object ?arm) (mode floss-machine off)))                      ; derived from the microtheory
  (:causal (:regime material-process) (:microtheory floss-machine)
           (:template (held -tilt-> flowing[tilt > repose-angle] -untilt-> poured)))
  (:phases (phase over   (goal (above (tagged spout ?object) ?destination)) (giskard CartesianPose))
           (phase tilt   (goal (tilted ?object)) (monitor flow) (giskard FullBodyControlled))
           (phase untilt (terminal (contains ?destination ?amount)))))

(def-action-schema gathering
  (:specializes transferring)
  (:roles (tool (the candy-stick (held-by ?arm))) (container (a floss-pan)) (substance (some floss)))
  (:telos (:over ?i) (achieve (on-tool ?substance ?tool) :at (end ?i))              ; CandyStage gathered
                     (maintain (held-by ?tool ?arm) :during ?i))
  (:pre   (and (portion-spun floss-machine) (held-by ?tool ?arm)))
  (:causal (:regime material-process) (:microtheory floss-machine))
  (:failures (not-enough-floss NotEnoughFloss))
  (:phases (phase sweep (goal (tool-path ?tool (circle-in ?container))) (giskard ToolPath))
           (phase lift  (terminal (gathered ?substance ?tool)))))

(def-action-schema wrapping
  (:specializes substance-manipulation)
  (:roles (tool (the candy-stick (held-by ?arm))) (above (a floss-pan)))
  (:telos (:over ?i) (achieve (stage (the cotton-candy (on ?tool)) wrapped) :at (end ?i))
                     (maintain (held-by ?tool ?arm) :during ?i))
  (:causal (:regime material-process))
  (:phases (phase figure-eights (goal (tool-path ?tool (figure-eight-above ?above))) (giskard ToolPath)
                  (terminal wrapped))))

(def-action-schema handing-over
  (:specializes interaction-action)
  (:roles (object (the candy-stick (held-by ?arm))) (recipient (the customer)) (destination (a handover-location)))
  (:telos (:over ?i) (achieve (holds ?recipient ?object) :at (end ?i))
                     (maintain (held-by ?object ?arm) :until (taken-by ?recipient ?object))   ; release only on take-over
                     (prevent (dropped ?object) :during ?i))
  (:pre   (and (held-by ?object ?arm) (reachable-for ?recipient ?destination)))
  (:causal (:regime contact-transmission))                                         ; release only on take-over
  (:phases (phase present (goal (at ?object ?destination)) (giskard CartesianPose))
           (phase release (goal (released ?object)) (monitor (taken-by ?recipient)) (terminal received))))

(def-action-schema wiping
  (:specializes surface-treatment)
  (:roles (tool (a sponge (held-by ?arm))) (surface (a surface)))
  (:pre    (at (the robot) (the station (tag at-machine))))                     ; the controls / the pan are reached from the machine
  (:telos (:over ?i) (achieve (clean ?surface) :at (end ?i))
                     (maintain (held-by ?tool ?arm) :during ?i))
  (:causal (:regime contact-transmission))
  (:phases (phase strokes (goal (tool-path ?tool (wipe ?surface))) (giskard WipingAction) (terminal clean))))

(def-action-schema monitoring-process
  (:specializes perception-action)
  (:roles (process (a process)) (until (a condition)) (timeout (a duration)))
  (:telos (:over ?i) (monitor (mode ?process) :until ?until)
                     (achieve ?until :within ?timeout))
  (:causal (:microtheory floss-machine))                                           ; waits on the executable model
  (:phases (phase wait (monitor ?until) (terminal observed)))
  (:failures (phase-not-reached PhaseNotReached)))

;;; ================================================================================================================
;;; 6. Plan schemas: the booth's top-level designators as generalized plan schemata (HADL 00-schemata:
;;;    pre / body / eff / succ / monitor / repair). Bodies follow actions.py and make-and-hand-over.lisp.
;;; ================================================================================================================

(def-plan-schema fill-spinner-head ((machine cotton-candy-machine) (sugar sugar-carton) (arm arm))
  (:pre    (and (mode floss-machine off) (gripper-free ?arm)))
  (:body   (seq (:tag take   (perform (an action (type transporting) (object ?sugar) (arm ?arm))))
                (evap-protect
                  (seq (:tag go-close (with-failure-handling
                                          ((navigation-blocked (f) (wait-for (path-clear)) (retry)))   ; a person in the way
                                        (perform (an action (type navigating) (destination (the station (tag machine-close)))))))
                       (:tag pour (perform (an action (type pouring-into) (object ?sugar)
                                             (destination (tagged spinner-head ?machine))
                                             (amount (some substance (mass portion-batch)))))))
                  (seq (:tag go-back (with-failure-handling
                                         ((navigation-blocked (f) (wait-for (path-clear)) (retry)))
                                       (perform (an action (type navigating) (destination (the station (tag at-machine)))))))
                       (:tag put-back (perform (an action (type putting-down) (object ?sugar)
                                                 (destination (its destination)))))))))   ; never put down from close
  (:escapes process-failure)                                                      ; to the caller (shift level)
  (:eff    (>= (sugar-in-head ?machine) (* fill-fraction head-capacity)))
  (:succ   (and (gripper-free ?arm) (>= (sugar-in-head ?machine) portion-sugar)))     ; model-only: sugar is not seen
  (:monitor (mode floss-machine))
  (:repair ((spilled (some sugar) floor) -> (achieve (clean floor)))))

(def-plan-schema start-machine ((machine cotton-candy-machine) (arm arm))
  (:pre    (and (gripper-free ?arm) (>= (sugar-in-head ?machine) portion-sugar)))   ; empty head + heat = running-empty
  (:body   (seq (perform (an action (type pressing-button) (object (tagged motor-switch ?machine)) (state on)))
                (wait-for (elapsed master-to-heat-delay))
                (perform (an action (type pressing-button) (object (tagged heat-switch ?machine)) (state on)))
                (perform (an action (type turning) (object (tagged heat-control ?machine)) (setting 1.0)))
                (perform (an action (type monitoring-process) (process floss-machine) (until (mode floss-machine producing))))
                (perform (an action (type turning) (object (tagged heat-control ?machine)) (setting 0.7)))))  ; operating heat
  (:escapes process-failure)                                                       ; machine faults: the caller decides
  (:succ   (mode floss-machine producing)))

(def-plan-schema stop-machine ((machine cotton-candy-machine) (arm arm))
  (:body   (seq (perform (an action (type pressing-button) (object (tagged heat-switch ?machine)) (state off)))
                (perform (an action (type monitoring-process) (process floss-machine) (until (mode floss-machine spinning))))
                (perform (an action (type pressing-button) (object (tagged motor-switch ?machine)) (state off)))
                (perform (an action (type monitoring-process) (process floss-machine) (until (mode floss-machine off))))))
  (:escapes process-failure)
  (:succ   (mode floss-machine off)))

(def-plan-schema make-cotton-candy ((candy cotton-candy) (stick candy-stick) (machine cotton-candy-machine) (arm arm))
  (:pre    (and (mode floss-machine producing) (enough-sugar ?machine)
                (at (the robot) (the station (tag at-machine)))))         ; sticks and pan are reached from there
  (:body   (with-failure-handling
               ((head-running-empty (f)                     ; Q2, during service: a fault -- repair, then retry
                  (perform (an action (type putting-down) (object ?stick) (destination (its destination))))  ; free
                  (perform-plan stop-machine ?machine ?arm)   ; refilling needs mode off (pouring into a spinning
                  (perform-plan fill-spinner-head ?machine (a sugar-carton) ?arm)   ; head is prohibited)
                  (perform-plan start-machine ?machine ?arm)
                  (retry))
                (not-enough-floss (f)
                  (perform (an action (type monitoring-process) (process floss-machine) (until (portion-spun))))
                  (retry)))
             (seq (:tag take-stick (perform (an action (type transporting) (object ?stick) (arm ?arm))))
                  (protect (held-by ?stick ?arm) :until (delivered ?candy))
                  (perform (an action (type monitoring-process) (process floss-machine) (until (portion-spun))))
                  (:tag gather (perform (an action (type gathering) (tool ?stick) (container (tagged floss-pan ?machine)))))
                  (:tag wrap   (perform (an action (type wrapping) (tool ?stick) (above (tagged floss-pan ?machine))))))))
  (:escapes process-failure)              ; a fault during the repair itself (or a phase timeout) goes to the shift
  (:succ   (stage ?candy wrapped)))

(def-plan-schema serve-cotton-candy ((candy cotton-candy) (stick candy-stick) (customer customer) (arm arm))
  (:pre    (and (stage ?candy wrapped) (held-by ?stick ?arm)))
  (:body   (seq (with-failure-handling
                    ((navigation-blocked (f) (wait-for (path-clear)) (retry)))
                  (perform (an action (type navigating) (destination (the station (tag serving))))))
                (evap-protect
                  (:tag hand-over (perform (an action (type handing-over) (object ?stick) (recipient ?customer)
                                             (destination (the handover-location (reachable-for ?customer))))))
                  (equate ?candy (the cotton-candy (held-by ?customer))))))                       ; D3: co-reference
  (:succ   (delivered ?candy ?customer)))

(def-plan-schema clean-floss-machine ((machine cotton-candy-machine) (arm arm))
  (:pre    (mode floss-machine off))                                              ; never wipe a spinning head
  (:body   (seq (perform (an action (type transporting) (object (the sponge))))
                (perform (an action (type wiping) (tool (the sponge)) (surface (tagged floss-pan ?machine))))
                (perform (an action (type putting-down) (object (the sponge)) (destination (its destination))))))
  (:succ   (clean (tagged floss-pan ?machine))))

;; closing: the same failure is the intended event (Q2) -- the burn-out cleans the head
(def-plan-schema close-for-the-day ((machine cotton-candy-machine) (arm arm))
  (:pre    (mode floss-machine producing))
  (:body   (with-failure-handling
               ((head-running-empty (f) (continue)))                ; burn-out: progress, not a fault (whole closing)
             (seq (perform (an action (type turning) (object (tagged heat-control ?machine)) (setting 1.0)))   ; burn out at
                  (perform (an action (type monitoring-process) (process floss-machine) (until (burnt-out ?machine))))  ; max heat
                  (perform-plan stop-machine ?machine ?arm)
                  (perform-plan clean-floss-machine ?machine ?arm)
                  (achieve (at (each tool) (its destination))))))
  (:escapes phase-not-reached)
  (:succ   (and (mode floss-machine off) (clean (tagged floss-pan ?machine)))))

;; the shift as one plan (M1): fill, start, make and serve one order, close
(def-plan-schema booth-shift ((machine cotton-candy-machine) (sugar sugar-carton) (stick candy-stick)
                              (candy cotton-candy) (customer customer) (arm arm))
  (:body   (seq (:tag fill  (perform-plan fill-spinner-head ?machine ?sugar ?arm))
                (:tag start (perform-plan start-machine ?machine ?arm))
                (:tag make  (perform-plan make-cotton-candy ?candy ?stick ?machine ?arm))
                (:tag serve (perform-plan serve-cotton-candy ?candy ?stick ?customer ?arm))
                (:tag close (perform-plan close-for-the-day ?machine ?arm))))
  (:escapes process-failure)
  (:succ   (and (delivered ?candy ?customer) (mode floss-machine off))))

;; one order: make a portion on a free stick, hand it to the customer who ordered it
(def-plan-schema serve-one-order ((machine cotton-candy-machine) (arm arm) (stick candy-stick) (candy cotton-candy)
                                  (customer customer))
  (:body   (seq (:tag make  (perform-plan make-cotton-candy ?candy ?stick ?machine ?arm))
                (:tag serve (perform-plan serve-cotton-candy ?candy ?stick ?customer ?arm))))
  (:escapes process-failure)
  (:succ   (delivered ?candy ?customer)))

;; a shift with two orders (M1): the head may run empty between them -- the service handler repairs (Q2)
(def-plan-schema booth-two-orders ((machine cotton-candy-machine) (sugar sugar-carton) (arm arm))
  (:body   (seq (:tag fill    (perform-plan fill-spinner-head ?machine ?sugar ?arm))
                (:tag start   (perform-plan start-machine ?machine ?arm))
                (:tag order-1 (perform-plan serve-one-order ?machine ?arm))
                (:tag order-2 (perform-plan serve-one-order ?machine ?arm))
                (:tag close   (perform-plan close-for-the-day ?machine ?arm))))
  (:escapes process-failure)
  (:succ   (mode floss-machine off)))

;; the generalized plan stays as it is (make-and-hand-over.lisp): its triangle-table rows perform these schemas.

;;; ================================================================================================================
;;; 7. The servant table: who fills which kind of role in the climb (D3 bind), cheapest sufficient first.
;;;    cost: ILLUSTRATIVE ordinal (1 lookup, 2 query, 3 emulation, 4 needs an action, 5 needs a person).
;;;    status: the binding status the servant yields (KR3 plausibility order recorded > anchored > commonsense > assumed)
;;; ================================================================================================================

(def-servant-table booth-servants
  ;; role kind                       servant (cost, status)                      source in the twin
  (part-of-reference                (sdt-part-tree 1 recorded)                   ; (tagged spinner-head machine) -> tag table
                                    )
  (object-by-type                   (eql-annotations 2 recorded)                 ; an(entity(variable(CandyStick, ...)))
                                    (perception-anchor 4 anchored)               ; DetectAction (simulated: ground truth)
                                    (open-world-assume 2 assumed))               ; Skolem stick until perceived
  (object-by-content                (ontology-recipes 2 recorded)                ; the-sugar-for: carton containing the ingredients
                                    (abstain 5 none))                            ; no carton -> GOAL-UNACHIEVABLE
  (customer                         (order-record 1 recorded)                    ; ordered-by in the candy belief
                                    (perception-anchor 4 anchored)               ; a human at the sales front
                                    (open-world-assume 2 assumed))
  (robot-station                    (layout-stations 1 recorded))                ; ROBOT_STATIONS (layout model)
  (destination-its                  (belonging-norm 2 recorded)                  ; D7: context serving / closed
                                    (class-home 1 commonsense)
                                    (storage-zone 2 commonsense)
                                    (ask 5 none))                                ; MP3: abstain and ask
  (handover-location                (eql-reachability 2 recorded))               ; reachable-for customer and robot
  (setting                          (manual 1 recorded))                         ; heat control 1.0 / 0.7 (GM_MAN_EXP)
  (amount                           (recipe 1 commonsense))                      ; portion 0.020 kg, batch 0.9 x 0.060 kg
  (grasp                            (grasp-candidates 2 recorded)                ; HasGraspCandidates (root frame!)
                                    (emulation-trial 3 recorded))                ; coraplex copied-world trial
  (process-prediction               (process-emulation 3 recorded))              ; FlossMachineProcess.advance_until
  (corridor                         (microtheory 3 derived)))                    ; D8 (no force channel in the baseline)

;;; ================================================================================================================
;;; 8. The gate per category (D6): how each of the 8 admissibility conditions is computed at the booth
;;; ================================================================================================================

(def-admissibility booth-gate
  (grounded             (every-role-bound :status-at-least assumed) (showable-in cramera))   ; KR3 groundedness
  (feasible             (reachable (giskard-trial)) (graspable (grasp-candidates)))
  (mechanism-compatible (regime-of-schema matches regime-of-microtheory))
  (effect-expected      (emulation (copied-world kinematics) (process floss-machine)) (:min-p 0.9))
  (invariant-preserving (not (enters closing-event)) (protections hold))                    ; floss-machine closing events
  (monitorable          (each-phase-has (or monitor terminal-check)))
  (has-fallback         (repair or retry or abstain))
  (in-scope             (in-boundary booth-shift)))

;;; Typical pre-act verdicts at the booth (D4): which options compete
;;;   before pour-into : act-now | probe (look-at motor-switch) when P(mode off) < 0.98 | abstain
;;;   before hand-over : act-now | probe (look-at customer) when the customer binding is assumed, not anchored
;;;   before gather    : act-now | wait (monitoring-process portion-spun) when the emulated floss < portion
