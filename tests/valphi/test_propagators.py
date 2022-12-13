from clingo import Control

from valphi.propagators import val_phi_as_weight_constraints


def test_val_phi_as_wc():
    controller = Control("0")
    controller.add("base", [], """
        sub_type(l2_1,l1_1,"1").
        sub_type(l2_1,l1_2,"-1").
        
        val(0..3).
        class(C) :- sub_type(C,_,_).
        class(C) :- sub_type(_,C,_).
        {eval(C,V) : val(V)} = 1 :- class(C).
    """)
    controller.ground([("base", [])])
    wc = val_phi_as_weight_constraints(controller.symbolic_atoms, "l2_1", [-2, 0, 2], ordered_encoding=False)
    assert '\n'.join(wc) == """
:- #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)} <= -2, not eval(l2_1,0).
:- not #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)} <= -2, eval(l2_1,0).
:- -2 < #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)} <= 0, not eval(l2_1,1).
:- not -2 < #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)} <= 0, eval(l2_1,1).
:- 0 < #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)} <= 2, not eval(l2_1,2).
:- not 0 < #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)} <= 2, eval(l2_1,2).
:- 2 < #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)}, not eval(l2_1,3).
:- not 2 < #sum{1,l1_1,1 : eval(l1_1,1); 2,l1_1,2 : eval(l1_1,2); 3,l1_1,3 : eval(l1_1,3); -1,l1_2,1 : eval(l1_2,1); -2,l1_2,2 : eval(l1_2,2); -3,l1_2,3 : eval(l1_2,3)}, eval(l2_1,3).
    """.strip()

    wc = val_phi_as_weight_constraints(controller.symbolic_atoms, "l2_1", [-2, 0, 2], ordered_encoding=True)
    assert '\n'.join(wc) == """
:- #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)} <= -2, not eval(l2_1,0).
:- not #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)} <= -2, eval(l2_1,0).
:- -2 < #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)} <= 0, not eval(l2_1,1).
:- not -2 < #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)} <= 0, eval(l2_1,1).
:- 0 < #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)} <= 2, not eval(l2_1,2).
:- not 0 < #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)} <= 2, eval(l2_1,2).
:- 2 < #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)}, not eval(l2_1,3).
:- not 2 < #sum{1,l1_1,1 : eval_ge(l1_1,1); 1,l1_1,2 : eval_ge(l1_1,2); 1,l1_1,3 : eval_ge(l1_1,3); -1,l1_2,1 : eval_ge(l1_2,1); -1,l1_2,2 : eval_ge(l1_2,2); -1,l1_2,3 : eval_ge(l1_2,3)}, eval(l2_1,3).
    """.strip()
