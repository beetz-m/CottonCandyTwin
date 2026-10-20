;;; make-and-hand-over.lisp -- the generalized cotton candy plan as an RPL/CRAM plan.
;;;
;;; A Lisp rendering of cotton_candy/universal_plan.py (the executable version, run by
;;; `cram/run.sh pytest tests/test_universal_plan.py`). The sub-goal tags, goals, kernels and
;;; methods below correspond one to one to MakeAndHandOverCandyPlan.steps();
;;; tests/test_plan_lisp.py checks that the tags and their order match.
;;;
;;; Design lineage
;;;   Beetz, Concurrent Reactive Plans (LNAI 1772, 2000): the plan is a generalized plan, a
;;;     reactive routine that achieves its goal from any state in which a kernel holds.
;;;     It is written with ACHIEVE, PERFORM, WITH-POLICY, PROTECTION, :TAG,
;;;     WITH-FAILURE-HANDLING and EVAP-PROTECT.
;;;   Fikes, Hart & Nilsson (1972), triangle tables: each sub-goal i has a kernel, which is the
;;;     condition under which steps i..n achieve the goal. PLANEX executes the
;;;     highest-numbered sub-goal whose kernel holds.
;;;   Schoppers (1987), universal plans: the plan maps every belief state to an action.
;;;   Firby (1989), RAPs: each sub-goal is a task with a success test and alternative methods.
;;;
;;; Designators use the entity designator language (ResearchSpace okf/cram/designator-language):
;;;   (a/an SORT SLOT*)  attributive: any entity that matches
;;;   (the  SORT SLOT*)  referential: exactly one entity, tracked, equate-able
;;;   (some substance ...)  stuff      (each SORT ...)  universal
;;; Entity designators are matched against the belief state, which is the candy belief store
;;; plus the booth's scene graph. They are re-resolved in every cycle, so "the stick" denotes
;;; a free stick in the quiver before the robot takes one, and the held stick afterwards.

(in-package :cotton-candy)

;;; ------------------------------------------------------------------------------------------
;;; 1. The entity designators of the service (designators.py: ServiceDesignators)
;;; ------------------------------------------------------------------------------------------

(def-entity-designator the-candy ()
  "The candy I am making: the one ordered portion that is not delivered yet.
   Two open orders make it ambiguous, and THE fails with MULTIPLE-SOLUTIONS-FOUND."
  (the object (type cotton-candy)
              (stage (not delivered))
              (flavour ?flavour)
              (ordered-by ?who)))

(def-entity-designator the-stick-of (?candy)
  "The stick the candy is on. Before the candy is on a stick: the empty stick in hand,
   else a free stick in the quiver."
  (first-of
    (the object (type candy-stick) (carries ?candy))
    (an  object (type candy-stick) (attached-to (the object (tool-frame-of (the agent (= self))))))
    (an  object (type candy-stick) (in (the object (type stick-quiver))))))

(def-entity-designator the-ingredients-of (?candy)
  "The ingredients of the candy: the ontology's materials named in its order (recipes.py)."
  (each substance (ingredient-of ?candy)))

(def-entity-designator the-sugar-for (?candy)
  "The sugar for the candy: a carton whose contents include every ingredient of the candy.
   No match (e.g. blueberry while only raspberry flossugar is in the booth) leaves the
   MACHINE-READY kernel false, and the plan fails with GOAL-UNACHIEVABLE."
  (a object (type sugar-carton)
            (contains (the-ingredients-of ?candy))))

(def-entity-designator the-customer-of (?candy)
  "The customer the candy is for (any customer if the order names none)."
  (if (desig-prop-value ?candy :ordered-by)
      (the agent (type human) (name (desig-prop-value ?candy :ordered-by)))
      (an  agent (type human) (at (the location (type sales-front))))))

(def-entity-designator the-machine ()
  (the object (type cotton-candy-machine)))

(def-entity-designator the-handover-location (?customer)
  (the location (in (the object (type handover-zone)))
                (reachable-for ?customer)
                (reachable-for (the agent (= self)))))

;;; ------------------------------------------------------------------------------------------
;;; 2. Belief fluents (universal_plan.py: BeliefEstimator / ServiceBelief)
;;;    Fluents are estimated from the belief state. Nothing is read from the plan's own
;;;    history, so the plan works from whatever state it is started in.
;;; ------------------------------------------------------------------------------------------

(def-belief-fluent gripper-free  (?arm)    (not (held-by ?arm)))
(def-belief-fluent sugar-available (?candy) (resolvable (the-sugar-for ?candy)))
(def-belief-fluent enough-sugar  (?m)      (>= (sugar-in-head ?m) (portion-sugar ?m)))  ; 60 g CALIBRATED
(def-belief-fluent producing     (?m)      (eq (phase ?m) :producing))
(def-belief-fluent stick-in-hand (?s ?arm) (eq (held-by ?arm) ?s))
(def-belief-fluent candy-stage   (?candy)  (desig-prop-value ?candy :stage))  ; none gathered wrapped delivered
(def-belief-fluent delivered     (?candy ?c) (and (eq (candy-stage ?candy) :delivered)
                                                  (holds ?c (the-stick-of ?candy))))

;;; A believed portion whose stick is not in the robot's hand is lost: the estimator resets
;;; its stage to NONE, so the plan starts that candy again (test_a_believed_portion_without_
;;; its_stick_in_hand_is_lost).

;;; ------------------------------------------------------------------------------------------
;;; 3. Manipulation-category routines: the methods' building blocks
;;;    (manipulation_categories.py + actions.py; each is an action designator)
;;; ------------------------------------------------------------------------------------------

(def-cram-function fill-spinner-head (?machine ?sugar ?arm)
  "Fill: transporting the carton, pouring into the spinner head, putting the carton down.
   Irreversible once the sugar flows, so the carton is put back under EVAP-PROTECT."
  (perform (an action (type moving-torso) (state high)))
  (perform (an action (type transporting)
                      (object ?sugar)
                      (arm ?arm)
                      (approach towards-sales-front)))
  (evap-protect
      (seq (perform (an action (type navigating)
                               (destination (the location (type robot-station) (name machine-close)))))
           (perform (an action (type pouring-into)
                               (object ?sugar)
                               (destination (the object (part-of ?machine) (type spinner-head)))
                               (amount (some substance (contains (the-ingredients-of (the-candy)))
                                                       (mass portion-batch))))))
    (perform (an action (type navigating)
                        (destination (the location (type robot-station) (name machine)))))
    (perform (an action (type putting-down)
                        (object ?sugar)
                        (destination (a location (on (the object (type work-table)))))))))

(def-cram-function start-machine (?machine ?arm)
  "Start: pressing the motor switch, pressing the heat switch, turning the heat control
   (manual pp. 9-10: motor first, then heat, full heat to warm up, then operating heat)."
  (perform (an action (type moving-torso) (state low)))
  (perform (an action (type pressing-button)
                      (object (the object (part-of ?machine) (type motor-switch)))
                      (arm ?arm) (state on)))
  (wait-for (process-time-elapsed ?machine master-to-heat-delay))
  (perform (an action (type pressing-button)
                      (object (the object (part-of ?machine) (type heat-switch)))
                      (arm ?arm) (state on)))
  (perform (an action (type turning)
                      (object (the object (part-of ?machine) (type heat-control)))
                      (arm ?arm) (setting 1.0)))
  (wait-for (eq (phase ?machine) :producing))
  (perform (an action (type turning)
                      (object (the object (part-of ?machine) (type heat-control)))
                      (arm ?arm) (setting operating-heat))))

(def-cram-function refill-spinner-head (?machine ?sugar ?arm)
  "Refill: stop, fill and start (the head is only filled while the machine is off)."
  (perform (an action (type stopping-machine) (machine ?machine) (arm ?arm)))
  (fill-spinner-head ?machine ?sugar ?arm)
  (start-machine ?machine ?arm))

;;; ------------------------------------------------------------------------------------------
;;; 4. The sub-goals: a triangle table of ACHIEVE routines
;;;    Each row has a tag, a goal (checked before acting), a kernel, RAP methods and an
;;;    optional protection that it establishes for the later rows.
;;; ------------------------------------------------------------------------------------------

(def-triangle-table make-and-hand-over-table (?candy ?arm)
  ;; Bound by WITH-DESIGNATORS in MAKE-AND-HAND-OVER; re-resolved each cycle.
  (:designators ?stick ?sugar ?customer ?machine)

  (0 free-gripper
     :goal    (gripper-free ?arm)
     :kernel  t
     :methods ((perform (an action (type putting-down)
                                   (object (the object (held-by ?arm)))
                                   (destination (the location (home-of (the object (held-by ?arm)))))))))

  (1 machine-ready
     :goal    (and (producing ?machine) (enough-sugar ?machine))
     :kernel  (and (gripper-free ?arm) (sugar-available ?candy))
     :methods ((try-in-order
                 (when (and (eq (phase ?machine) :off) (not (enough-sugar ?machine)))
                   (fill-spinner-head ?machine ?sugar ?arm)
                   (start-machine ?machine ?arm))
                 (when (eq (phase ?machine) :off)
                   (start-machine ?machine ?arm))
                 (when (not (enough-sugar ?machine))
                   (refill-spinner-head ?machine ?sugar ?arm))
                 (when (not (producing ?machine))
                   (start-machine ?machine ?arm)))))

  (2 stick-in-hand
     :goal    (stick-in-hand ?stick ?arm)
     :kernel  (and (gripper-free ?arm) (producing ?machine) (enough-sugar ?machine)
                   (resolvable ?stick))
     :methods ((perform (an action (type moving-torso) (state low)))
               (perform (an action (type transporting)
                                   (object ?stick)
                                   (arm ?arm)
                                   (approach towards-left-wall))))
     ;; From here on the stick must stay in the hand until the candy is delivered.
     :protects (or (stick-in-hand ?stick ?arm) (delivered ?candy ?customer)))

  (3 candy-formed
     :goal    (member (candy-stage ?candy) '(:wrapped :delivered))
     :kernel  (and (stick-in-hand ?stick ?arm) (eq (candy-stage ?candy) :none)
                   (producing ?machine) (enough-sugar ?machine))
     :methods ((wait-for (portion-spun ?machine))
               (perform (an action (type gathering)
                                   (tool ?stick) (arm ?arm)
                                   (container (the object (part-of ?machine) (type floss-pan)))))
               (perform (an action (type wrapping)
                                   (tool ?stick) (arm ?arm)
                                   (above (the object (part-of ?machine) (type floss-pan)))))))

  (4 candy-wrapped
     :goal    (member (candy-stage ?candy) '(:wrapped :delivered))
     :kernel  (and (stick-in-hand ?stick ?arm) (eq (candy-stage ?candy) :gathered))
     :methods ((perform (an action (type wrapping)
                                   (tool ?stick) (arm ?arm)
                                   (above (the object (part-of ?machine) (type floss-pan)))))))

  (5 handed-over
     :goal    (delivered ?candy ?customer)
     :kernel  (and (stick-in-hand ?stick ?arm) (eq (candy-stage ?candy) :wrapped)
                   (resolvable ?customer))
     :methods ((perform (an action (type navigating)
                                   (destination (the location (type robot-station) (name serving)))))
               ;; Irreversible: the candy leaves the robot. The belief update is protected.
               (evap-protect
                   (perform (an action (type handing-over)
                                       (object ?stick) (arm ?arm)
                                       (recipient ?customer)
                                       (destination (the-handover-location ?customer))))
                 (equate ?candy (the object (type cotton-candy) (held-by ?customer))))
               (perform (an action (type navigating)
                                   (destination (the location (type robot-station) (name machine))))))))

;;; ------------------------------------------------------------------------------------------
;;; 5. The generalized plan: check the goal, re-resolve, select by kernel (PLANEX), act,
;;;    protect, recover
;;; ------------------------------------------------------------------------------------------

(def-top-level-cram-function make-and-hand-over (&key (?arm :right) (max-cycles 14) (max-retries 2))
  "Make the candy I am making and hand it to the customer it is for, from whatever state
   the candy, the robot and the booth are in."
  (let ((retries (make-hash-table)))
    (:tag service
      (loop repeat max-cycles do
        ;; Re-resolve every designator against the current belief state.
        (with-designators ((?candy    (the-candy))
                           (?stick    (the-stick-of ?candy))
                           (?sugar    (the-sugar-for ?candy))
                           (?customer (the-customer-of ?candy))
                           (?machine  (the-machine)))
          ;; Check before acting: the goal already holds, so there is nothing to do.
          (when (delivered ?candy ?customer)
            (return-from make-and-hand-over ?candy))
          ;; PLANEX: the highest-numbered sub-goal whose kernel holds and whose goal does not.
          (let ((row (select-by-kernel make-and-hand-over-table)))
            (unless row
              (fail 'goal-unachievable :candy ?candy))
            (with-policy (whenever (protection-violated (active-protections))
                           (fail 'protection-violation :tag (violated-protection-tag)))
              (with-failure-handling
                  ((goal-unachievable (e) (declare (ignore e)) nil)       ; propagate
                   (multiple-solutions-found (e) (declare (ignore e)) nil) ; ambiguous THE: propagate
                   (plan-failure (e)
                     (when (<= (incf (gethash (row-tag row) retries 0)) max-retries)
                       (warn "sub-goal ~a failed (~a), re-resolving" (row-tag row) e)
                       ;; Return to the loop: re-estimate the belief, re-resolve the designators,
                       ;; re-select a row. Another row may now apply.
                       (return))))
                (achieve-row row)
                (when (row-protects row)
                  (protect (row-protects row) :until (delivered ?candy ?customer)))))))))
    (fail 'goal-unachievable :reason "goal not reached within max-cycles")))

;;; ------------------------------------------------------------------------------------------
;;; Traces from the executable version (kinematic PR2, tests/test_universal_plan.py)
;;;   cold machine        MACHINE-READY  STICK-IN-HAND  CANDY-FORMED  HANDED-OVER
;;;   stick already taken                               CANDY-FORMED  HANDED-OVER
;;;   wrapped candy in hand                                           HANDED-OVER
;;;   second order        (machine ready) STICK-IN-HAND CANDY-FORMED  HANDED-OVER
;;;   goal already holds  ()
;;;   blueberry ordered   GOAL-UNACHIEVABLE (no sugar for the candy)
;;;   two open orders     MULTIPLE-SOLUTIONS-FOUND (THE candy is ambiguous)
;;;
;;; Differences from the Python version (see universal_plan.py "Limitation")
;;;   * WITH-POLICY/WHENEVER makes the protection a concurrent fluent monitor. In Python it is
;;;     checked at step boundaries only.
;;;   * In Python, the methods of MACHINE-READY are a conditional (_make_ready), not
;;;     TRY-IN-ORDER over guarded alternatives.
;;; ------------------------------------------------------------------------------------------
