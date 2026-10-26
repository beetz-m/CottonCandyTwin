;;; Rules of the booth's knowledge base (def-rule): state-dependent knowledge, forward-chained over the observed
;;; atoms before every goal check, gate and verdict. Axioms that do not depend on the state live in ontology/booth.ttl.

(def-rule spinner-head-hot
  "The heating element is on and turned up: the head and the pan around it are hot (no touching, no water)."
  (:if (switch-state heat-switch on) (travel-fraction heat-control ?f) (> ?f 0.1))
  (:then (hot spinner-head) (hot floss-pan)))

(def-rule spinner-head-moving
  "The motor turns the head whenever its switch is on (the phase may still be warming up)."
  (:if (switch-state motor-switch on))
  (:then (moving spinner-head)))

(def-rule open-order
  "An order whose candy has not been delivered yet."
  (:if (stage ?candy ?stage) (member ?stage (none gathered wrapped)))
  (:then (open-order ?candy)))

(def-rule ready-to-hand-over
  "A wrapped candy on a stick the robot holds can be handed over."
  (:if (stage ?candy wrapped) (on-tool floss ?stick) (held-by ?stick ?arm))
  (:then (ready-to-hand-over ?candy ?arm)))

(def-rule booth-idle
  "Nothing to do: no open order and the machine is off."
  (:if (mode floss-machine off) (not (open-order ?candy)))
  (:then (idle booth)))
